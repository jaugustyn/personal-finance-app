import { PageHeader } from "@/components/page-header";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export default function AssetsPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Portfel"
        description="Moduł aktywów jest w przebudowie"
      />

      <Card>
        <CardHeader>
          <CardTitle>Moduł aktywów jest w przebudowie</CardTitle>
          <CardDescription>
            Obecna wersja aplikacji nie udostępnia obsługi portfela aktywów.
          </CardDescription>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          Wyceny, historia portfela i wizualizacje zostaną udostępnione po
          zakończeniu przebudowy modułu.
        </CardContent>
      </Card>
    </div>
  );
}
