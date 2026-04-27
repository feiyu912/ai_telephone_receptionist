"use client";

import { cn } from "@/lib/utils";
import { useClickOutside } from "@/hooks/use-click-outside";
import {
  createContext,
  type Dispatch,
  type PropsWithChildren,
  type SetStateAction,
  useContext,
  useEffect,
  useRef,
} from "react";

type DropdownContextType = {
  isOpen: boolean;
  handleOpen: () => void;
  handleClose: () => void;
};

const DropdownContext = createContext<DropdownContextType | null>(null);

function useDropdownContext() {
  const ctx = useContext(DropdownContext);
  if (!ctx) {
    throw new Error("useDropdownContext must be used within a Dropdown");
  }
  return ctx;
}

type DropdownProps = {
  children: React.ReactNode;
  isOpen: boolean;
  setIsOpen: Dispatch<SetStateAction<boolean>>;
};

export function Dropdown({ children, isOpen, setIsOpen }: DropdownProps) {
  const triggerRef = useRef<HTMLElement | null>(null);

  const handleClose = () => setIsOpen(false);
  const handleOpen = () => setIsOpen(true);

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === "Escape") handleClose();
  };

  useEffect(() => {
    if (isOpen) {
      triggerRef.current = document.activeElement as HTMLElement;
    } else {
      setTimeout(() => triggerRef.current?.focus(), 0);
    }
  }, [isOpen]);

  return (
    <DropdownContext.Provider value={{ isOpen, handleOpen, handleClose }}>
      <div className="relative" onKeyDown={handleKeyDown}>
        {children}
      </div>
    </DropdownContext.Provider>
  );
}

type DropdownContentProps = {
  align?: "start" | "end" | "center";
  className?: string;
  children: React.ReactNode;
};

export function DropdownContent({
  children,
  align = "center",
  className,
}: DropdownContentProps) {
  const { isOpen, handleClose } = useDropdownContext();

  const contentRef = useClickOutside<HTMLDivElement>(() => {
    if (isOpen) handleClose();
  });

  if (!isOpen) return null;

  return (
    <div
      ref={contentRef}
      role="menu"
      aria-orientation="vertical"
      className={cn(
        "absolute z-50 mt-2 min-w-[8rem] origin-top-right rounded-lg",
        align === "end" && "right-0",
        align === "start" && "left-0",
        align === "center" && "left-1/2 -translate-x-1/2",
        className,
      )}
    >
      {children}
    </div>
  );
}

type DropdownTriggerProps = React.HTMLAttributes<HTMLButtonElement> & {
  children: React.ReactNode;
};

export function DropdownTrigger({ children, className, ...rest }: DropdownTriggerProps) {
  const { handleOpen, isOpen } = useDropdownContext();

  return (
    <button
      type="button"
      className={className}
      onClick={handleOpen}
      aria-expanded={isOpen}
      aria-haspopup="menu"
      data-state={isOpen ? "open" : "closed"}
      {...rest}
    >
      {children}
    </button>
  );
}

export function DropdownClose({ children }: PropsWithChildren) {
  const { handleClose } = useDropdownContext();
  return <div onClick={handleClose}>{children}</div>;
}
