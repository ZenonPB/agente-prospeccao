export type LeadUsefulnessReason =
  | 'EMPRESA_ERRADA'
  | 'SEM_NECESSIDADE'
  | 'CONTATO_ERRADO'
  | 'FORA_DO_PORTE'
  | 'FORA_DA_REGIAO'
  | 'JA_TEM_FORNECEDOR'
  | 'DADOS_INCORRETOS'
  | 'OUTRO';

export interface LeadUsefulnessFeedbackResult {
  id: string;
  lead_id: string;
  useful: boolean;
  reason: LeadUsefulnessReason | null;
  updated: boolean;
}

export const LEAD_USEFULNESS_REASONS: { value: LeadUsefulnessReason; label: string }[] = [
  { value: 'EMPRESA_ERRADA', label: 'Empresa errada' },
  { value: 'SEM_NECESSIDADE', label: 'Sem necessidade agora' },
  { value: 'CONTATO_ERRADO', label: 'Contato errado' },
  { value: 'FORA_DO_PORTE', label: 'Fora do porte' },
  { value: 'FORA_DA_REGIAO', label: 'Fora da região' },
  { value: 'JA_TEM_FORNECEDOR', label: 'Já tem fornecedor' },
  { value: 'DADOS_INCORRETOS', label: 'Dados incorretos' },
  { value: 'OUTRO', label: 'Outro motivo' },
];