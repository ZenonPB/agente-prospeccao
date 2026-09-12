"use client";

export const ACTIVE_ORGANIZATION_STORAGE_KEY = "active_organization_id";
export const ORGANIZATION_STORAGE_VERSION_KEY = "org_storage_v1";
export const ORGANIZATION_STORAGE_VERSION = "1";
export const ACTIVE_ORGANIZATION_CHANGED_EVENT = "active-organization-changed";

function ensureStorageVersion(): void {
  if (typeof window === "undefined") return;
  const version = window.localStorage.getItem(ORGANIZATION_STORAGE_VERSION_KEY);
  if (version === ORGANIZATION_STORAGE_VERSION) return;

  window.localStorage.removeItem(ACTIVE_ORGANIZATION_STORAGE_KEY);
  window.localStorage.setItem(
    ORGANIZATION_STORAGE_VERSION_KEY,
    ORGANIZATION_STORAGE_VERSION,
  );
}

export function getActiveOrganizationId(): string | null {
  if (typeof window === "undefined") return null;
  ensureStorageVersion();
  return window.localStorage.getItem(ACTIVE_ORGANIZATION_STORAGE_KEY);
}

export function getServerActiveOrganizationId(): null {
  return null;
}

export function setActiveOrganizationId(organizationId: string): void {
  if (typeof window === "undefined") return;
  ensureStorageVersion();

  const current = window.localStorage.getItem(ACTIVE_ORGANIZATION_STORAGE_KEY);
  if (current === organizationId) return;

  window.localStorage.setItem(ACTIVE_ORGANIZATION_STORAGE_KEY, organizationId);
  window.dispatchEvent(
    new CustomEvent(ACTIVE_ORGANIZATION_CHANGED_EVENT, {
      detail: { organizationId },
    }),
  );
}

export function isActiveOrganizationStorageEvent(event: StorageEvent): boolean {
  return event.storageArea === window.localStorage
    && event.key === ACTIVE_ORGANIZATION_STORAGE_KEY;
}

/**
 * Assina mudanças do workspace tanto na aba atual quanto em outras abas.
 * Compatível com `useSyncExternalStore`, evitando duplicar estado React e
 * localStorage no seletor.
 */
export function subscribeToActiveOrganization(onStoreChange: () => void): () => void {
  if (typeof window === "undefined") return () => undefined;

  const handleCustomEvent = () => onStoreChange();
  const handleStorage = (event: StorageEvent) => {
    if (isActiveOrganizationStorageEvent(event)) onStoreChange();
  };

  window.addEventListener(ACTIVE_ORGANIZATION_CHANGED_EVENT, handleCustomEvent);
  window.addEventListener("storage", handleStorage);

  return () => {
    window.removeEventListener(ACTIVE_ORGANIZATION_CHANGED_EVENT, handleCustomEvent);
    window.removeEventListener("storage", handleStorage);
  };
}
