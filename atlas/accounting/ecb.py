"""European Central Bank (ECB) currency exchange rate provider and cache (Phase 9)."""

from __future__ import annotations

import logging
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas.data.models import ECBExchangeRate

logger = logging.getLogger(__name__)

# Fallback realistic baseline rate if network and DB are completely empty
DEFAULT_EUR_USD_RATE = Decimal("1.085000")


class ECBRateProvider:
    """Manages official ECB foreign exchange reference rates for tax reporting and EUR conversions."""

    def __init__(self, session: Session | None = None) -> None:
        self.session = session
        self._memory_cache: dict[tuple[date, str, str], Decimal] = {}

    def get_rate(
        self,
        rate_date: date | datetime,
        base_currency: str = "EUR",
        target_currency: str = "USD",
    ) -> Decimal:
        """Get official ECB exchange rate for date (Base Currency to Target Currency).

        For EUR/USD, a rate of 1.0850 means 1 EUR = 1.0850 USD.
        """
        d = rate_date.date() if isinstance(rate_date, datetime) else rate_date
        base = base_currency.upper()
        target = target_currency.upper()

        if base == target:
            return Decimal("1.000000")

        key = (d, base, target)
        if key in self._memory_cache:
            return self._memory_cache[key]

        # 1. Check Database if session available
        if self.session is not None:
            stmt = select(ECBExchangeRate).where(
                ECBExchangeRate.rate_date == d,
                ECBExchangeRate.base_currency == base,
                ECBExchangeRate.target_currency == target,
            )
            row = self.session.execute(stmt).scalar_one_or_none()
            if row is not None:
                rate = Decimal(str(row.rate))
                self._memory_cache[key] = rate
                return rate

            # If exact date is weekend/holiday, fetch the most recent prior trading day rate
            prior_stmt = (
                select(ECBExchangeRate)
                .where(
                    ECBExchangeRate.rate_date < d,
                    ECBExchangeRate.base_currency == base,
                    ECBExchangeRate.target_currency == target,
                )
                .order_by(ECBExchangeRate.rate_date.desc())
                .limit(1)
            )
            prior_row = self.session.execute(prior_stmt).scalar_one_or_none()
            if prior_row is not None:
                rate = Decimal(str(prior_row.rate))
                self._memory_cache[key] = rate
                return rate

        # 2. Return fallback default rate if not yet ingested
        rate = DEFAULT_EUR_USD_RATE
        self._memory_cache[key] = rate
        return rate

    def convert_usd_to_eur(self, amount_usd: Decimal, rate_date: date | datetime) -> Decimal:
        """Convert USD amount to EUR using the ECB reference rate on rate_date."""
        rate = self.get_rate(rate_date, base_currency="EUR", target_currency="USD")
        if rate <= Decimal("0"):
            rate = DEFAULT_EUR_USD_RATE
        # EUR = USD / (USD per EUR)
        return amount_usd / rate

    def convert_eur_to_usd(self, amount_eur: Decimal, rate_date: date | datetime) -> Decimal:
        """Convert EUR amount to USD using the ECB reference rate on rate_date."""
        rate = self.get_rate(rate_date, base_currency="EUR", target_currency="USD")
        return amount_eur * rate

    def store_rate(
        self,
        rate_date: date | datetime,
        rate: Decimal,
        base_currency: str = "EUR",
        target_currency: str = "USD",
    ) -> ECBExchangeRate | None:
        """Store or update an ECB reference rate in the database."""
        d = rate_date.date() if isinstance(rate_date, datetime) else rate_date
        base = base_currency.upper()
        target = target_currency.upper()
        self._memory_cache[(d, base, target)] = rate

        if self.session is None:
            return None

        stmt = select(ECBExchangeRate).where(
            ECBExchangeRate.rate_date == d,
            ECBExchangeRate.base_currency == base,
            ECBExchangeRate.target_currency == target,
        )
        existing = self.session.execute(stmt).scalar_one_or_none()
        if existing is not None:
            existing.rate = rate
            existing.fetched_at = datetime.now(UTC)
            self.session.commit()
            return existing

        record = ECBExchangeRate(
            rate_date=d,
            base_currency=base,
            target_currency=target,
            rate=rate,
            fetched_at=datetime.now(UTC),
        )
        self.session.add(record)
        self.session.commit()
        return record

    def fetch_ecb_daily_rates(self) -> int:
        """Fetch latest daily rates from the official ECB XML RSS feed."""
        url = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "ATLAS/1.5 (Autonomous Trading System)"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                xml_data = resp.read()
            root = ET.fromstring(xml_data)
            namespaces = {
                "gesmes": "http://www.gesmes.org/xml/2002-08-01",
                "ns": "http://www.ecb.int/vocabulary/2002-08-01/eurofxref",
            }
            cube_time = root.find(".//ns:Cube[@time]", namespaces)
            if cube_time is None:
                return 0
            time_str = cube_time.attrib["time"]
            rate_date = datetime.strptime(time_str, "%Y-%m-%d").date()

            count = 0
            for cube in cube_time.findall("ns:Cube", namespaces):
                curr = cube.attrib.get("currency")
                rate_val = cube.attrib.get("rate")
                if curr and rate_val:
                    self.store_rate(
                        rate_date=rate_date,
                        rate=Decimal(rate_val),
                        base_currency="EUR",
                        target_currency=curr,
                    )
                    count += 1
            return count
        except Exception as ex:
            logger.warning("Failed to fetch ECB daily rates from web feed: %s", ex)
            return 0
