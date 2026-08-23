"use client";

import { useState, ReactNode } from "react";
import { HelpCircle } from "lucide-react";

interface InfoTooltipProps {
  content: string | ReactNode;
  title?: string;
  className?: string;
  side?: "top" | "bottom" | "left" | "right";
  children?: ReactNode;
}

export function InfoTooltip({
  content,
  title,
  className = "",
  side = "top",
  children,
}: InfoTooltipProps) {
  const [visible, setVisible] = useState(false);

  // Fallback text if content is somehow empty
  const displayContent = content || title || "Information & Context";
  const displayTitle = title && content ? title : undefined;

  // Position styles
  let positionClass = "bottom-full left-1/2 -translate-x-1/2 mb-2";
  if (side === "bottom") positionClass = "top-full left-1/2 -translate-x-1/2 mt-2";
  if (side === "left") positionClass = "right-full top-1/2 -translate-y-1/2 mr-2";
  if (side === "right") positionClass = "left-full top-1/2 -translate-y-1/2 ml-2";

  return (
    <span
      className={`relative inline-flex items-center group cursor-help ${className}`}
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
      onFocus={() => setVisible(true)}
      onBlur={() => setVisible(false)}
    >
      {children ? (
        children
      ) : (
        <HelpCircle className="w-3.5 h-3.5 text-text-3 hover:text-pos transition-colors ml-1 inline-block shrink-0" />
      )}

      {visible && (
        <span
          className={`absolute z-[100] w-64 max-w-[85vw] p-2.5 bg-surface-2/95 backdrop-blur-md border border-border text-text-1 text-[11px] font-sans font-normal normal-case leading-relaxed rounded shadow-2xl pointer-events-none select-none transition-opacity ${positionClass}`}
          role="tooltip"
        >
          {displayTitle && (
            <span className="block font-mono font-semibold text-pos text-xs mb-1 uppercase tracking-wide">
              {displayTitle}
            </span>
          )}
          <span className="text-text-2">{displayContent}</span>
        </span>
      )}
    </span>
  );
}
