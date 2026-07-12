/* eslint-disable react-hooks/set-state-in-effect -- reset transient selection after controlled props commit */
"use client";

import { useEffect, useMemo, useState } from "react";
import { CalendarRange, ChevronLeft, ChevronRight, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";

interface DateRangePickerProps {
  from: string;
  to: string;
  onFromChange: (value: string) => void;
  onToChange: (value: string) => void;
  onClear?: () => void;
  ariaLabel: string;
}

type CalendarMode = "days" | "months" | "years";

export function DateRangePicker({
  from,
  to,
  onFromChange,
  onToChange,
  onClear,
  ariaLabel,
}: DateRangePickerProps) {
  const { t, locale } = useT();
  const [open, setOpen] = useState(false);
  const [calendarMode, setCalendarMode] = useState<CalendarMode>("days");
  const [draftFrom, setDraftFrom] = useState<Date | null>(null);
  const [draftRange, setDraftRange] = useState<{
    from: string;
    to: string;
  } | null>(null);
  const [visibleMonth, setVisibleMonth] = useState(() =>
    startOfMonth(parseDateValue(from) ?? new Date()),
  );
  const displayFrom = draftRange?.from ?? from;
  const displayTo = draftRange?.to ?? to;
  const selectedFrom = parseDateValue(displayFrom);
  const selectedTo = parseDateValue(displayTo);
  const activeFrom = draftFrom ?? selectedFrom;
  const activeTo = draftFrom ? null : selectedTo;
  const monthDays = useMemo(() => buildMonthDays(visibleMonth), [visibleMonth]);
  const label = rangeLabel(displayFrom, displayTo, t);
  const canClear = displayFrom !== "" || displayTo !== "" || draftFrom !== null;

  useEffect(() => {
    if (draftRange && draftRange.from === from && draftRange.to === to) {
      setDraftRange(null);
    }
  }, [draftRange, from, to]);

  useEffect(() => {
    if (!from && !to) {
      setDraftFrom(null);
      setDraftRange(null);
    }
  }, [from, to]);

  const handleOpenChange = (nextOpen: boolean) => {
    setOpen(nextOpen);
    if (nextOpen) {
      setDraftRange(null);
      setCalendarMode("days");
      setVisibleMonth(startOfMonth(selectedFrom ?? selectedTo ?? new Date()));
      setDraftFrom(selectedFrom && !selectedTo ? selectedFrom : null);
    }
  };

  const setRange = (nextFrom: string, nextTo: string) => {
    onFromChange(nextFrom);
    onToChange(nextTo);
  };

  const clearRange = () => {
    setDraftFrom(null);
    setDraftRange(null);
    if (onClear) {
      onClear();
      return;
    }
    setRange("", "");
  };

  const selectDay = (day: Date) => {
    const value = toDateValue(day);
    const rangeStart = draftFrom ?? (selectedTo ? null : selectedFrom);

    if (!rangeStart) {
      setDraftFrom(day);
      return;
    }

    const rangeStartValue = toDateValue(rangeStart);
    const nextFrom = day < rangeStart ? value : rangeStartValue;
    const nextTo = day < rangeStart ? rangeStartValue : value;

    setDraftFrom(null);
    setDraftRange({ from: nextFrom, to: nextTo });
    setRange(nextFrom, nextTo);
  };

  const applyPreset = (preset: "month" | "quarter" | "year") => {
    const today = new Date();
    const monthsBack = preset === "month" ? 0 : preset === "quarter" ? 2 : 11;
    const nextFrom = startOfMonth(addMonths(today, -monthsBack));
    const nextFromValue = toDateValue(nextFrom);
    const nextToValue = toDateValue(today);
    setDraftFrom(null);
    setDraftRange({ from: nextFromValue, to: nextToValue });
    setRange(nextFromValue, nextToValue);
    setVisibleMonth(startOfMonth(today));
    setCalendarMode("days");
    setOpen(false);
  };

  return (
    <Popover open={open} onOpenChange={handleOpenChange}>
      <div className="relative">
        <PopoverTrigger asChild>
          <Button
            type="button"
            variant="outline"
            className={cn(
              "w-full justify-start px-3 font-normal",
              canClear && "pr-9",
            )}
            aria-label={ariaLabel}
          >
            <CalendarRange className="h-4 w-4 text-muted-foreground" />
            <span className="truncate">{label}</span>
          </Button>
        </PopoverTrigger>
        {canClear ? (
          <button
            type="button"
            className="absolute right-1.5 top-1/2 z-10 flex h-6 w-6 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            aria-label={t("common.clear")}
            onClick={(event) => {
              event.preventDefault();
              event.stopPropagation();
              clearRange();
            }}
          >
            <X className="h-3.5 w-3.5" />
          </button>
        ) : null}
      </div>
      <PopoverContent align="start" className="w-[22rem] p-3">
        <div className="grid grid-cols-3 divide-x divide-border/70 overflow-hidden rounded-md bg-muted/45 p-1">
          <PresetButton onClick={() => applyPreset("month")}>
            {t("transactions.dateRange.thisMonth")}
          </PresetButton>
          <PresetButton onClick={() => applyPreset("quarter")}>
            {t("transactions.dateRange.last3Months")}
          </PresetButton>
          <PresetButton onClick={() => applyPreset("year")}>
            {t("transactions.dateRange.last12Months")}
          </PresetButton>
        </div>

        <div className="mt-3 rounded-md border p-2">
          <div className="mb-2 flex items-center justify-between gap-2">
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={() =>
                setVisibleMonth((value) =>
                  calendarMode === "years"
                    ? addYears(value, -12)
                    : calendarMode === "months"
                      ? addYears(value, -1)
                      : addMonths(value, -1),
                )
              }
              aria-label={t("transactions.dateRange.previousMonth")}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <CalendarHeader
              mode={calendarMode}
              month={visibleMonth}
              locale={locale}
              selectMonthLabel={t("transactions.dateRange.selectMonth")}
              selectYearLabel={t("transactions.dateRange.selectYear")}
              onModeChange={setCalendarMode}
            />
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={() =>
                setVisibleMonth((value) =>
                  calendarMode === "years"
                    ? addYears(value, 12)
                    : calendarMode === "months"
                      ? addYears(value, 1)
                      : addMonths(value, 1),
                )
              }
              aria-label={t("transactions.dateRange.nextMonth")}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>

          {calendarMode === "days" && (
            <>
              <div className="grid grid-cols-7 gap-1 text-center text-[11px] font-medium text-muted-foreground">
                {weekdayLabels(locale).map((day) => (
                  <div key={day} className="py-1">
                    {day}
                  </div>
                ))}
              </div>
              <div className="mt-1 grid grid-cols-7 gap-1">
                {monthDays.map((day, index) =>
                  day ? (
                    <CalendarDay
                      key={toDateValue(day)}
                      day={day}
                      from={activeFrom}
                      to={activeTo}
                      onClick={() => selectDay(day)}
                    />
                  ) : (
                    <div key={`empty-${index}`} />
                  ),
                )}
              </div>
            </>
          )}

          {calendarMode === "months" && (
            <MonthGrid
              month={visibleMonth}
              locale={locale}
              onSelect={(month) => {
                setVisibleMonth(
                  new Date(visibleMonth.getFullYear(), month, 1),
                );
                setCalendarMode("days");
              }}
            />
          )}

          {calendarMode === "years" && (
            <YearGrid
              month={visibleMonth}
              onSelect={(year) => {
                setVisibleMonth(new Date(year, visibleMonth.getMonth(), 1));
                setCalendarMode("months");
              }}
            />
          )}
        </div>

      </PopoverContent>
    </Popover>
  );
}

function PresetButton({
  children,
  onClick,
}: {
  children: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className="flex h-8 min-w-0 items-center justify-center rounded-[5px] px-2 text-center text-xs font-medium text-muted-foreground transition-colors hover:bg-background hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      onClick={onClick}
    >
      {children}
    </button>
  );
}

function CalendarHeader({
  mode,
  month,
  locale,
  selectMonthLabel,
  selectYearLabel,
  onModeChange,
}: {
  mode: CalendarMode;
  month: Date;
  locale: "pl" | "en";
  selectMonthLabel: string;
  selectYearLabel: string;
  onModeChange: (mode: CalendarMode) => void;
}) {
  if (mode === "years") {
    return (
      <div className="text-sm font-medium">
        {yearRangeLabel(month)}
      </div>
    );
  }

  if (mode === "months") {
    return (
      <button
        type="button"
        className="rounded-md px-2 py-1 text-sm font-medium transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        aria-label={selectYearLabel}
        onClick={() => onModeChange("years")}
      >
        {month.getFullYear()}
      </button>
    );
  }

  return (
    <div className="flex items-center gap-1">
      <button
        type="button"
        className="rounded-md px-2 py-1 text-sm font-medium capitalize transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        aria-label={selectMonthLabel}
        onClick={() => onModeChange("months")}
      >
        {formatMonthName(month, locale)}
      </button>
      <button
        type="button"
        className="rounded-md px-2 py-1 text-sm font-medium transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        aria-label={selectYearLabel}
        onClick={() => onModeChange("years")}
      >
        {month.getFullYear()}
      </button>
    </div>
  );
}

function MonthGrid({
  month,
  locale,
  onSelect,
}: {
  month: Date;
  locale: "pl" | "en";
  onSelect: (month: number) => void;
}) {
  const activeMonth = month.getMonth();
  return (
    <div className="grid grid-cols-3 gap-1">
      {monthLabels(locale).map((label, index) => (
        <button
          key={label}
          type="button"
          className={cn(
            "h-9 rounded-md text-sm font-medium capitalize transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            index === activeMonth &&
              "bg-primary text-primary-foreground hover:bg-primary hover:text-primary-foreground",
          )}
          onClick={() => onSelect(index)}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

function YearGrid({
  month,
  onSelect,
}: {
  month: Date;
  onSelect: (year: number) => void;
}) {
  const activeYear = month.getFullYear();
  const start = yearPageStart(activeYear);
  const years = Array.from({ length: 12 }, (_, index) => start + index);

  return (
    <div className="grid grid-cols-4 gap-1">
      {years.map((year) => (
        <button
          key={year}
          type="button"
          className={cn(
            "h-9 rounded-md text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            year === activeYear &&
              "bg-primary text-primary-foreground hover:bg-primary hover:text-primary-foreground",
          )}
          onClick={() => onSelect(year)}
        >
          {year}
        </button>
      ))}
    </div>
  );
}

function CalendarDay({
  day,
  from,
  to,
  onClick,
}: {
  day: Date;
  from: Date | null;
  to: Date | null;
  onClick: () => void;
}) {
  const selectedStart = Boolean(from && sameDay(day, from));
  const selectedEnd = Boolean(to && sameDay(day, to));
  const inRange = Boolean(from && to && day > from && day < to);
  const today = sameDay(day, new Date());

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex h-8 items-center justify-center rounded-md text-sm transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        inRange && "bg-primary/10 text-foreground",
        (selectedStart || selectedEnd) &&
          "bg-primary text-primary-foreground hover:bg-primary hover:text-primary-foreground",
        today && !selectedStart && !selectedEnd && "ring-1 ring-border",
      )}
    >
      {day.getDate()}
    </button>
  );
}

function rangeLabel(from: string, to: string, t: ReturnType<typeof useT>["t"]) {
  if (from && to) return `${formatDateValue(from)} - ${formatDateValue(to)}`;
  if (from) {
    return t("transactions.dateRange.from", {
      value: formatDateValue(from),
    });
  }
  if (to) {
    return t("transactions.dateRange.to", {
      value: formatDateValue(to),
    });
  }
  return t("transactions.dateRange.any");
}

function parseDateValue(value: string) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return null;
  const date = new Date(
    Number(match[1]),
    Number(match[2]) - 1,
    Number(match[3]),
  );
  return Number.isNaN(date.getTime()) ? null : date;
}

function toDateValue(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function formatDateValue(value: string) {
  const [year, month, day] = value.split("-");
  if (!year || !month || !day) return value;
  return `${day}.${month}.${year}`;
}

function startOfMonth(date: Date) {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

function addMonths(date: Date, amount: number) {
  return new Date(date.getFullYear(), date.getMonth() + amount, 1);
}

function addYears(date: Date, amount: number) {
  return new Date(date.getFullYear() + amount, date.getMonth(), 1);
}

function buildMonthDays(month: Date) {
  const first = startOfMonth(month);
  const daysInMonth = new Date(
    first.getFullYear(),
    first.getMonth() + 1,
    0,
  ).getDate();
  const mondayOffset = (first.getDay() + 6) % 7;
  const days: Array<Date | null> = Array.from(
    { length: mondayOffset },
    () => null,
  );
  for (let day = 1; day <= daysInMonth; day += 1) {
    days.push(new Date(first.getFullYear(), first.getMonth(), day));
  }
  return days;
}

function sameDay(left: Date, right: Date) {
  return (
    left.getFullYear() === right.getFullYear() &&
    left.getMonth() === right.getMonth() &&
    left.getDate() === right.getDate()
  );
}

function formatMonthName(date: Date, locale: "pl" | "en") {
  return new Intl.DateTimeFormat(locale === "pl" ? "pl-PL" : "en-US", {
    month: "long",
  }).format(date);
}

function monthLabels(locale: "pl" | "en") {
  return Array.from({ length: 12 }, (_, month) =>
    new Intl.DateTimeFormat(locale === "pl" ? "pl-PL" : "en-US", {
      month: "short",
    }).format(new Date(2026, month, 1)),
  );
}

function yearPageStart(year: number) {
  return Math.floor(year / 12) * 12;
}

function yearRangeLabel(month: Date) {
  const start = yearPageStart(month.getFullYear());
  return `${start} - ${start + 11}`;
}

function weekdayLabels(locale: "pl" | "en") {
  return locale === "pl"
    ? ["Pn", "Wt", "Sr", "Cz", "Pt", "So", "Nd"]
    : ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
}
