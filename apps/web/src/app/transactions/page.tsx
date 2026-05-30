"use client";

import { useState } from "react";
import { useT } from "@/lib/i18n";
import { GroupsView } from "./_components/groups-view";
import { ListView } from "./_components/list-view";
import { ViewSwitcher } from "./_components/view-switcher";
import type { TransactionsView } from "./_lib/constants";

export default function TransactionsPage() {
  const { t } = useT();
  const [view, setView] = useState<TransactionsView>("list");

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">
          {t("transactions.title")}
        </h1>
        <ViewSwitcher value={view} onChange={setView} />
      </div>

      {view === "groups" ? (
        <GroupsView />
      ) : (
        <ListView key={view} reviewMode={view === "review"} />
      )}
    </div>
  );
}
