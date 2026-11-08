import type { ReactNode } from 'react';
import type { BackboneCatalog } from './telcoBackboneTypes';

/** Parent folder for generated file paths (e.g. incoming/bss/slug/file.csv → incoming/bss/slug) */
export function destinationFolderFromPath(path: string | undefined): string {
  if (!path) return '';
  const n = path.replace(/\\/g, '/').trim();
  const i = n.lastIndexOf('/');
  if (i <= 0) return '/';
  return n.slice(0, i);
}

/** Match backend: incoming/{layer}/{slug}/... */
export function inferSystemKeyFromFilePath(catalog: BackboneCatalog, path: string | undefined): string | null {
  if (!path) return null;
  const parts = path.replace(/\\/g, '/').split('/').filter(Boolean);
  if (parts[0] !== 'incoming' || parts.length < 3) return null;
  const slug = parts[2];
  const row = catalog.systems.find((r) => r.slug === slug);
  return row?.system_key ?? null;
}

export function resolveProductFamily(
  catalog: BackboneCatalog,
  systemKey: string | null | undefined,
  filePath?: string | null,
): { key: string; slug?: string } | null {
  const key = (systemKey && systemKey.trim()) || inferSystemKeyFromFilePath(catalog, filePath || undefined);
  if (!key) return null;
  const slug = catalog.systems.find((r) => r.system_key === key)?.slug;
  return { key, slug };
}

export function vendorLabel(catalog: BackboneCatalog, code: string): string {
  const label = catalog.vendors[code];
  return label ? `${label} (${code})` : code;
}

export function vendorBadge(catalog: BackboneCatalog, code: string | null | undefined): ReactNode {
  if (!code) return null;
  const label = catalog.vendors[code];
  if (!label) return <span className="text-muted-foreground">({code})</span>;
  return (
    <span className="text-muted-foreground">
      {label} ({code})
    </span>
  );
}
