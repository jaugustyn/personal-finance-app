"use client";

import { useEffect, useState } from "react";
import { useT } from "@/lib/i18n";
import { PageHeader } from "@/components/page-header";
import { GroupsView } from "./_components/groups-view";
import { ListView } from "./_components/list-view";
import { ViewSwitcher } from "./_components/view-switcher";
import type { TransactionsView } from "./_lib/constants";

export default function TransactionsPage() {
  const { t } = useT();
  const [view, setView] = useState<TransactionsView>("list");
  const [initialSearch, setInitialSearch] = useState("");

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setInitialSearch(params.get("search") ?? "");
    if (params.get("view") === "review") setView("review");
    if (params.get("view") === "groups") setView("groups");
  }, []);

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("transactions.title")}
        actions={<ViewSwitcher value={view} onChange={setView} />}
      />

      {view === "groups" ? (
        <GroupsView />
      ) : (
        <ListView
          key={`${view}:${initialSearch}`}
          reviewMode={view === "review"}
          initialSearch={initialSearch}
        />
      )}
    </div>
  );
}
