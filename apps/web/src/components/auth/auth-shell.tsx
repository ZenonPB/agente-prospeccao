import { Radar, ScanSearch, CalendarCheck } from "lucide-react";
import { BrandMark } from "@/components/layout/brand-mark";

const highlights = [
  {
    icon: Radar,
    title: "Encontre leads prontos",
    text: "Coleta automática de empresas em qualquer cidade e segmento.",
  },
  {
    icon: ScanSearch,
    title: "Qualifique com critério",
    text: "Inteligência artificial pontua cada oportunidade e explica o porquê.",
  },
  {
    icon: CalendarCheck,
    title: "Acompanhe até a reunião",
    text: "Kanban, mensagens e follow-ups em um único lugar.",
  },
];

/**
 * Painel de identidade do fluxo de autenticação: assinatura visual do radar
 * (varredura de sinais) + propostas de valor do produto, do lado esquerdo.
 */
export function AuthShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid min-h-screen bg-background lg:grid-cols-2">
      {/* Painel de marca (radar) */}
      <div className="relative hidden overflow-hidden bg-sidebar text-sidebar-foreground lg:flex lg:flex-col">
        {/* Luzes ambientes */}
        <div className="pointer-events-none absolute -left-32 -top-32 h-96 w-96 rounded-full bg-sidebar-primary/25 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-40 -right-40 h-[28rem] w-[28rem] rounded-full bg-accent/15 blur-3xl" />

        <div className="relative z-10 flex flex-1 flex-col justify-center p-12 xl:p-16">
          <div className="flex items-center gap-3">
            <BrandMark className="h-9 w-9 text-sidebar-primary" />
            <div>
              <p className="text-base font-semibold tracking-tight">Agente Prospecção</p>
              <p className="text-xs text-sidebar-foreground/50">Inteligência comercial</p>
            </div>
          </div>

          <div className="mt-14 max-w-md">
            <h2 className="font-heading text-3xl font-semibold leading-tight tracking-tight xl:text-4xl">
              O radar da sua prospecção
            </h2>
            <p className="mt-4 text-sm leading-relaxed text-sidebar-foreground/70">
              Encontre empresas que precisam do que você vende, entenda o que
              importa e chegue primeiro — do primeiro contato à reunião marcada.
            </p>
          </div>

          <div className="mt-12 space-y-5">
            {highlights.map((item) => (
              <div key={item.title} className="flex items-start gap-4">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-sidebar-accent text-sidebar-primary">
                  <item.icon className="h-5 w-5" aria-hidden="true" />
                </div>
                <div>
                  <p className="text-sm font-medium">{item.title}</p>
                  <p className="text-sm text-sidebar-foreground/60">{item.text}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        <p className="relative z-10 px-12 pb-10 text-xs text-sidebar-foreground/40">
          © {new Date().getFullYear()} Agente Prospecção — feito para a sua empresa.
        </p>
      </div>

      {/* Formulário */}
      <div className="flex items-center justify-center p-4 sm:p-8">
        <div className="flex w-full max-w-md flex-col">
          <div className="mb-8 flex items-center justify-center gap-2.5 lg:hidden">
            <BrandMark className="h-7 w-7 text-primary" />
            <span className="font-heading text-lg font-semibold tracking-tight">
              Agente Prospecção
            </span>
          </div>
          {children}
        </div>
      </div>
    </div>
  );
}
