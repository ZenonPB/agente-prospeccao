"use client";

import Image from "next/image";
import { Radar, ScanSearch, CalendarCheck, ChevronLeft, ChevronRight } from "lucide-react";
import { BrandMark } from "@/components/layout/brand-mark";
import { useTheme } from "next-themes";
import { useState, useEffect, useSyncExternalStore } from "react";

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

const teamPhotos = [
  {
    src: "/imgs/alphamec/nortear.jpg",
    caption: "Equipe AlphaMec no Evento Nortear",
  },
  {
    src: "/imgs/alphamec/foto2.jpg",
    caption: "Time AlphaMec em ação",
  },
  {
    src: "/imgs/alphamec/foto3.jpg",
    caption: "Inovação e engenharia de ponta",
  },
];

const members = [
  { src: "/imgs/alphamec/yasmin.png", name: "Zenon" },
];

/**
 * Painel de identidade do fluxo de autenticação. No tema AlphaMec exibe a
 * marca (logo, fotos da equipe e membros) sobre fundo claro; nos demais temas
 * mantém a assinatura visual do radar (varredura de sinais) + propostas de
 * valor.
 */
export function AuthShell({ children }: { children: React.ReactNode }) {
  const { theme } = useTheme();
  const mounted = useSyncExternalStore(
    () => () => {},
    () => true,
    () => false,
  );
  const [photoIndex, setPhotoIndex] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setPhotoIndex((i) => (i + 1) % teamPhotos.length);
    }, 4500);
    return () => clearInterval(timer);
  }, []);

  const isAlpha = mounted && theme === "alpha";

  return (
    <div className="grid min-h-screen bg-background lg:grid-cols-2">
      {/* Painel de marca */}
      <div
        className={`relative hidden overflow-hidden lg:flex lg:flex-col ${
          isAlpha
            ? "border-r border-[#910001]/10 text-[#4c0000]"
            : "bg-sidebar text-sidebar-foreground"
        }`}
        style={
          isAlpha
            ? {
                backgroundImage:
                  "radial-gradient(circle at 18% 12%, rgba(145,0,1,0.07) 0, transparent 46%), linear-gradient(to right, rgba(145,0,1,0.045) 1px, transparent 1px), linear-gradient(to bottom, rgba(145,0,1,0.045) 1px, transparent 1px)",
                backgroundSize: "auto, 2.5rem 2.5rem, 2.5rem 2.5rem",
                backgroundPosition: "center",
                backgroundColor: "#fffaf8",
              }
            : undefined
        }
      >
        {/* Luzes ambientes */}
        {isAlpha ? (
          <>
            <div className="pointer-events-none absolute -left-32 -top-32 h-96 w-96 rounded-full bg-[#910001]/5 blur-3xl" />
            <div className="pointer-events-none absolute -bottom-40 -right-40 h-[28rem] w-[28rem] rounded-full bg-[#7c0000]/5 blur-3xl" />
          </>
        ) : (
          <>
            <div className="pointer-events-none absolute -left-32 -top-32 h-96 w-96 rounded-full bg-sidebar-primary/25 blur-3xl" />
            <div className="pointer-events-none absolute -bottom-40 -right-40 h-[28rem] w-[28rem] rounded-full bg-accent/15 blur-3xl" />
          </>
        )}

        <div className="relative z-10 flex flex-1 flex-col justify-between p-12 xl:p-16">
          <div className="flex items-center gap-3">
            {isAlpha ? (
              <>
                <Image
                  src="/imgs/alphamec/logo-alphamec.png"
                  alt="AlphaMec Logo"
                  width={40}
                  height={40}
                  className="h-10 w-10 object-contain"
                  priority
                />
                <div>
                  <p className="text-md font-semibold tracking-tight text-[#4c0000]">
                    Agente Prospecção
                  </p>
                  <p className="text-xs font-medium uppercase tracking-widest text-[#910001]">
                    por AlphaMec
                  </p>
                </div>
              </>
            ) : (
              <BrandMark className="h-9 w-9 text-sidebar-primary" />
            )}
            {!isAlpha && (
              <div>
                <p className="text-base font-semibold tracking-tight">Agente Prospecção</p>
                <p className="text-xs text-sidebar-foreground/50">Inteligência comercial</p>
              </div>
            )}
          </div>

          <div className="my-auto max-w-md space-y-8">
            <div className="space-y-4">
              <h2
                className={`font-heading text-3xl font-bold leading-tight tracking-tight xl:text-4xl ${
                  isAlpha
                    ? "bg-gradient-to-r from-[#4c0000] to-[#910001] bg-clip-text text-transparent"
                    : ""
                }`}
              >
                {isAlpha
                  ? "Conexão inteligente com o mercado"
                  : "O radar da sua prospecção"}
              </h2>
              <p
                className={`text-sm leading-relaxed ${
                  isAlpha ? "text-[#630201]/80" : "text-sidebar-foreground/70"
                }`}
              >
                {isAlpha
                  ? "Um sistema próprio da nossa manada, pensado para tornar a prospecção mais simples e dar mais força ao nosso time comercial. Aqui, encontramos novas oportunidades, organizamos os contatos e acompanhamos cada negociação de perto, do primeiro contato até a reunião."
                  : "Encontre empresas que precisam do que você vende, entenda o que importa e chegue primeiro — do primeiro contato à reunião marcada."}
              </p>
            </div>

            {/* Carrossel de fotos da equipe (tema AlphaMec) */}
            {isAlpha ? (
              <div className="group relative h-52 w-full overflow-hidden rounded-2xl border border-[#910001]/10 shadow-xl shadow-[#910001]/10">
                {teamPhotos.map((photo, i) => (
                  <Image
                    key={photo.src}
                    src={photo.src}
                    alt={photo.caption}
                    fill
                    sizes="(min-width: 1024px) 28rem, 100vw"
                    className={`object-cover transition-opacity duration-700 ${
                      i === photoIndex ? "opacity-100" : "opacity-0"
                    }`}
                  />
                ))}
                <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-[#4c0000]/85 via-transparent to-transparent" />
                <span className="absolute bottom-3 left-4 right-14 text-xs font-semibold uppercase tracking-wide text-white drop-shadow-md">
                  {teamPhotos[photoIndex].caption}
                </span>
                <div className="absolute bottom-3 right-3 flex items-center gap-1.5">
                  {teamPhotos.map((_, i) => (
                    <button
                      key={i}
                      type="button"
                      aria-label={`Foto ${i + 1}`}
                      onClick={() => setPhotoIndex(i)}
                      className={`h-1.5 rounded-full transition-all ${
                        i === photoIndex ? "w-4 bg-white" : "w-1.5 bg-white/50 hover:bg-white/80"
                      }`}
                    />
                  ))}
                </div>
                <button
                  type="button"
                  aria-label="Foto anterior"
                  onClick={() => setPhotoIndex((photoIndex - 1 + teamPhotos.length) % teamPhotos.length)}
                  className="absolute left-2 top-1/2 -translate-y-1/2 rounded-full bg-black/20 p-1 text-white opacity-0 transition-opacity hover:bg-black/40 group-hover:opacity-100"
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  aria-label="Próxima foto"
                  onClick={() => setPhotoIndex((photoIndex + 1) % teamPhotos.length)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 rounded-full bg-black/20 p-1 text-white opacity-0 transition-opacity hover:bg-black/40 group-hover:opacity-100"
                >
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            ) : null}

            <div className="space-y-5">
              {highlights.map((item) => (
                <div key={item.title} className="flex items-start gap-4">
                  <div
                    className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${
                      isAlpha
                        ? "bg-[#910001]/10 text-[#910001]"
                        : "bg-sidebar-accent text-sidebar-primary"
                    }`}
                  >
                    <item.icon className="h-5 w-5" aria-hidden="true" />
                  </div>
                  <div>
                    <p
                      className={`text-sm font-semibold ${
                        isAlpha ? "text-[#4c0000]" : ""
                      }`}
                    >
                      {item.title}
                    </p>
                    <p
                      className={`text-sm ${
                        isAlpha ? "text-[#630201]/70" : "text-sidebar-foreground/60"
                      }`}
                    >
                      {item.text}
                    </p>
                  </div>
                </div>
              ))}
            </div>

            {/* Galeria de membros (tema AlphaMec) */}
            {isAlpha ? (
              <div className="flex items-center gap-3 rounded-2xl border border-[#910001]/10 bg-white/70 p-3 pt-2.5 backdrop-blur-sm">
                <div className="flex -space-x-3">
                  {members.map((member) => (
                    <Image
                      key={member.src}
                      src={member.src}
                      alt={member.name}
                      title={member.name}
                      width={36}
                      height={36}
                      className="h-9 w-9 rounded-full border-2 border-white object-cover shadow-sm"
                    />
                  ))}
                </div>
                <span className="text-xs font-medium text-[#7c0000]/80">
                  Desenvolvido por Zenon para uso interno da AlphaMec
                </span>
              </div>
            ) : null}
          </div>

          <p
            className={`text-xs ${
              isAlpha ? "text-[#4c0000]/50" : "text-sidebar-foreground/40"
            }`}
          >
            © {new Date().getFullYear()} Agente Prospecção — feito para a sua empresa.
          </p>
        </div>
      </div>

      {/* Formulário */}
      <div
        className={`flex items-center justify-center p-4 sm:p-8 ${
          isAlpha ? "bg-gradient-to-br from-white to-red-50/10" : ""
        }`}
      >
        <div className="flex w-full max-w-md flex-col">
          <div className="mb-8 flex items-center justify-center gap-2.5 lg:hidden">
            {isAlpha ? (
              <>
                <Image
                  src="/imgs/alphamec/logo-alphamec.png"
                  alt="AlphaMec Logo"
                  width={32}
                  height={32}
                  className="h-8 w-8 object-contain"
                />
                <span className="font-heading text-lg font-semibold tracking-tight text-[#4c0000]">
                  Agente Prospecção
                </span>
              </>
            ) : (
              <BrandMark className="h-7 w-7 text-primary" />
            )}
            {!isAlpha && (
              <span className="font-heading text-lg font-semibold tracking-tight">
                Agente Prospecção
              </span>
            )}
          </div>
          {children}
        </div>
      </div>
    </div>
  );
}
