"use client";
import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import Accordion from "@mui/material/Accordion";
import AccordionDetails from "@mui/material/AccordionDetails";
import AccordionSummary from "@mui/material/AccordionSummary";
import Typography from "@mui/material/Typography";

interface PanelSectionProps {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}

export function PanelSection({ title, icon, children }: PanelSectionProps) {
  const [show, setShow] = useState(true);

  return (
    <Accordion
      expanded={show}
      onChange={() => setShow(!show)}
      disableGutters
      className="mb-5 overflow-hidden rounded-[22px] border border-stone-200/80 bg-white/80 shadow-[0_10px_30px_rgba(60,49,31,0.05)] before:hidden"
    >
      <AccordionSummary
        expandIcon={
          show ? (
            <ChevronDown className="h-4 w-4 text-stone-700" />
          ) : (
            <ChevronRight className="h-4 w-4 text-stone-700" />
          )
        }
        className="min-h-0 px-4 py-2 [&_.MuiAccordionSummary-content]:my-2"
      >
        <div className="flex items-center gap-3">
          <span className="rounded-xl bg-[#c7562a]/10 p-2 text-[#c7562a] shadow-sm">
            {icon}
          </span>
          <Typography className="text-base font-semibold text-stone-900">
            {title}
          </Typography>
        </div>
      </AccordionSummary>
      <AccordionDetails className="px-4 pb-4 pt-0">
        {children}
      </AccordionDetails>
    </Accordion>
  );
}
