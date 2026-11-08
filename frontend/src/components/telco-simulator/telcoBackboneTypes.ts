export type BackboneCatalog = {
  layer: string;
  vendors: Record<string, string>;
  vendor_default: string;
  systems: {
    system_key: string;
    slug: string;
    deliveries: string[];
  }[];
};
