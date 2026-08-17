'use client';

import { ConsultantProfile } from '@/components/relatorios/consultant-profile';

export default function ConsultantPage({ params }: { params: Promise<{ id: string }> }) {
  return <ConsultantProfile params={params} />;
}