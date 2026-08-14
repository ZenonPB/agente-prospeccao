'use client';

import { useMemo } from 'react';
import { MapContainer, TileLayer, CircleMarker, Tooltip as LeafletTooltip } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { AlertCircle } from 'lucide-react';
import type { AnalyticsGeoState } from '@/lib/api';

// Centroides aproximados das UFs brasileiras (lat, lng) — mapa por UF sem
// depender de API de geocodificação (offline, determinístico).
const UF_CENTROIDS: Record<string, [number, number]> = {
  AC: [-9.0, -70.0], AL: [-9.6, -36.7], AP: [1.0, -52.0], AM: [-4.0, -63.5],
  BA: [-12.6, -41.5], CE: [-5.2, -39.5], DF: [-15.8, -47.9], ES: [-19.2, -40.5],
  GO: [-15.8, -49.6], MA: [-5.5, -45.0], MT: [-12.0, -56.0], MS: [-20.4, -54.7],
  MG: [-18.5, -44.5], PA: [-4.0, -53.0], PB: [-7.1, -36.7], PR: [-24.7, -51.5],
  PE: [-8.4, -37.3], PI: [-6.5, -42.5], RJ: [-22.2, -42.6], RN: [-5.8, -36.5],
  RS: [-30.0, -53.0], RO: [-11.0, -63.0], RR: [2.0, -61.0], SC: [-27.3, -50.5],
  SP: [-22.5, -48.6], SE: [-10.6, -37.4], TO: [-10.0, -48.5],
};

const UF_NAMES: Record<string, string> = {
  AC: 'Acre', AL: 'Alagoas', AP: 'Amapá', AM: 'Amazonas', BA: 'Bahia', CE: 'Ceará',
  DF: 'Distrito Federal', ES: 'Espírito Santo', GO: 'Goiás', MA: 'Maranhão',
  MT: 'Mato Grosso', MS: 'Mato Grosso do Sul', MG: 'Minas Gerais', PA: 'Pará',
  PB: 'Paraíba', PR: 'Paraná', PE: 'Pernambuco', PI: 'Piauí', RJ: 'Rio de Janeiro',
  RN: 'Rio Grande do Norte', RS: 'Rio Grande do Sul', RO: 'Rondônia', RR: 'Roraima',
  SC: 'Santa Catarina', SP: 'São Paulo', SE: 'Sergipe', TO: 'Tocantins',
};

function scoreColor(score: number): string {
  if (score >= 75) return '#0f766e';
  if (score >= 60) return '#10b981';
  if (score >= 40) return '#f59e0b';
  return '#ef4444';
}

export function BrazilStateMap({ states }: { states: AnalyticsGeoState[] }) {
  const maxCount = useMemo(
    () => Math.max(1, ...states.map((s) => s.count || 0)),
    [states]
  );

  const markers = states
    .filter((s) => UF_CENTROIDS[s.state])
    .map((s) => {
      const [lat, lng] = UF_CENTROIDS[s.state];
      const radius = 6 + Math.sqrt(s.count / maxCount) * 14;
      return { ...s, lat, lng, radius };
    });

  return (
    <MapContainer
      center={[-14.5, -52.5]}
      zoom={4}
      scrollWheelZoom={false}
      className="h-full w-full rounded-lg"
      style={{ background: 'transparent' }}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {markers.map((m) => (
        <CircleMarker
          key={m.state}
          center={[m.lat, m.lng]}
          radius={m.radius}
          pathOptions={{
            color: '#ffffff',
            weight: 1,
            fillColor: scoreColor(m.avg_score),
            fillOpacity: 0.75,
          }}
        >
          <LeafletTooltip direction="top" offset={[0, -4]}>
            <div className="text-xs">
              <strong>{UF_NAMES[m.state] || m.state}</strong>
              <div>{m.count} leads · score {m.avg_score}</div>
              <div>{m.converted} convertidos</div>
            </div>
          </LeafletTooltip>
        </CircleMarker>
      ))}
    </MapContainer>
  );
}

export function GeoCard({ states }: { states: AnalyticsGeoState[] }) {
  return (
    <Card className="flex flex-col">
      <CardHeader>
        <CardTitle>Mapa de oportunidades</CardTitle>
        <CardDescription>
          Concentração de leads por estado. Quanto maior o círculo, mais leads; a cor reflete o score médio.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex-1">
        <div className="flex h-full min-h-[320px] flex-col gap-3">
          <div className="relative h-[300px] overflow-hidden rounded-lg border sm:h-[440px]">
            <BrazilStateMap states={states} />
          </div>
          <div className="flex flex-wrap items-center gap-3 text-[11px] text-muted-foreground">
            <span className="inline-flex items-center gap-1">
              <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: '#0f766e' }} /> Score ≥ 75
            </span>
            <span className="inline-flex items-center gap-1">
              <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: '#10b981' }} /> ≥ 60
            </span>
            <span className="inline-flex items-center gap-1">
              <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: '#f59e0b' }} /> ≥ 40
            </span>
            <span className="inline-flex items-center gap-1">
              <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: '#ef4444' }} /> &lt; 40
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export function GeoCardSkeleton() {
  return (
    <Card className="flex flex-col">
      <CardHeader>
        <Skeleton className="h-5 w-44" />
        <Skeleton className="h-4 w-72" />
      </CardHeader>
      <CardContent className="flex-1">
        <Skeleton className="h-[280px] w-full rounded-lg" />
      </CardContent>
    </Card>
  );
}

export function GeoCardError({ message }: { message: string }) {
  return (
    <Card className="flex flex-col">
      <CardHeader>
        <CardTitle>Mapa de oportunidades</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-center gap-2 text-red-600">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <p className="text-sm font-medium">Erro ao carregar mapa</p>
        </div>
        <p className="mt-1 text-xs text-red-500">{message}</p>
      </CardContent>
    </Card>
  );
}
