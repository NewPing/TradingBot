"use client";

import React, { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { WalkthroughModal } from "./WalkthroughModal";

interface WalkthroughContextType {
  isOpen: boolean;
  openWalkthrough: (initialStep?: number) => void;
  closeWalkthrough: () => void;
}

const WalkthroughContext = createContext<WalkthroughContextType | undefined>(undefined);

export function WalkthroughProvider({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);

  const openWalkthrough = (initialStep = 0) => {
    setCurrentStep(initialStep);
    setIsOpen(true);
  };

  const closeWalkthrough = () => {
    setIsOpen(false);
  };

  return (
    <WalkthroughContext.Provider value={{ isOpen, openWalkthrough, closeWalkthrough }}>
      {children}
      <WalkthroughModal
        isOpen={isOpen}
        initialStep={currentStep}
        onClose={closeWalkthrough}
      />
    </WalkthroughContext.Provider>
  );
}

export function useWalkthrough(): WalkthroughContextType {
  const context = useContext(WalkthroughContext);
  if (!context) {
    throw new Error("useWalkthrough must be used within a WalkthroughProvider");
  }
  return context;
}
