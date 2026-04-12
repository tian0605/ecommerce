import { Fragment, useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  createMediaUploadRequest,
  deleteProductMedia,
  fetchProduct,
  fetchProducts,
  resolveAssetUrl,
  sortProductMedia,
  updateProduct,
  updateProductSku,
  uploadMediaFile,
} from '../api';
import { useAuth } from '../auth';
import { WorkspaceSidebar } from '../components/WorkspaceSidebar';
import type { MediaAssetView, ProductDetail, ProductListItem, ProductSkuView, SiteListingView } from '../types';

type QuickFilterKey = 'all' | 'published' | 'listed' | 'optimized' | 'warning';
type ShopTab = { key: string; label: string; siteCode?: string; shopCode?: string; listing?: SiteListingView };
type DisplayAsset = {
  id: string;
  assetId?: number;
  url: string;
  label: string;
  kind: 'main' | 'sku' | 'legacy-main' | 'legacy-sku';
  skuId?: number | null;
  skuName?: string | null;
  uploadedAt?: string | null;
  deletable?: boolean;
  reorderable?: boolean;
};

const QUICK_FILTER_LABELS: Record<QuickFilterKey, string> = {
  all: '全部商品',
  published: '已发布',
  listed: '已上架',
  optimized: '已优化',
  warning: '库存预警',
};

const EDITABLE_STATUSES = ['collected', 'optimized', 'listed', 'published'];
const DEFAULT_SITE_CODES = ['TW', 'PH', 'VN', 'MY', 'SG'];
const PRODUCT_PAGE_SIZE = 10;

function buildVisiblePages(page: number, totalPages: number) {
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, index) => index + 1);
  }

  const pages = new Set<number>([1, totalPages, page - 1, page, page + 1]);
  if (page <= 3) {
    pages.add(2);
    pages.add(3);
    pages.add(4);
  }
  if (page >= totalPages - 2) {
    pages.add(totalPages - 1);
    pages.add(totalPages - 2);
    pages.add(totalPages - 3);
  }

  return Array.from(pages)
    .filter((value) => value >= 1 && value <= totalPages)
    .sort((left, right) => left - right);
}

function PaginationControls(props: { page: number; hasMore: boolean; total: number; pageSize: number; onPrev: () => void; onNext: () => void; onSelectPage: (page: number) => void }) {
  const totalPages = Math.max(1, Math.ceil(props.total / props.pageSize));
  const visiblePages = buildVisiblePages(props.page, totalPages);

  return (
    <div className="pagination-bar">
      <button className="ghost-button" onClick={props.onPrev} disabled={props.page <= 1}>上一页</button>
      {visiblePages.map((pageNumber, index) => {
        const previousPage = visiblePages[index - 1];
        const showGap = previousPage != null && pageNumber - previousPage > 1;
        return (
          <Fragment key={pageNumber}>
            {showGap ? <span className="pagination-gap">...</span> : null}
            <button
              className={`ghost-button page-number-button ${pageNumber === props.page ? 'active' : ''}`}
              onClick={() => props.onSelectPage(pageNumber)}
              disabled={pageNumber === props.page}
            >
              {pageNumber}
            </button>
          </Fragment>
        );
      })}
      <span>第 {props.page} / {totalPages} 页</span>
      <button className="ghost-button" onClick={props.onNext} disabled={!props.hasMore}>下一页</button>
    </div>
  );
}

function PageState(props: { title: string; detail: string; tone?: 'default' | 'error' }) {
  return (
    <div className={`state-card ${props.tone === 'error' ? 'error' : ''}`}>
      <div>
        <strong>{props.title}</strong>
        <p>{props.detail}</p>
      </div>
    </div>
  );
}

function normalizeText(value?: string | null) {
  return (value ?? '').trim().toLowerCase();
}

function toCurrency(value?: number | null) {
  if (value == null) {
    return '--';
  }
  return `¥${Number(value).toFixed(2)}`;
}

function formatDimensions(sku?: ProductSkuView | null) {
  const dims = [sku?.package_length, sku?.package_width, sku?.package_height]
    .map((value) => (value == null ? null : Number(value)))
    .filter((value): value is number => value != null && Number.isFinite(value) && value > 0);
  if (dims.length !== 3) {
    return '--';
  }
  return `${dims[0]} x ${dims[1]} x ${dims[2]} cm`;
}

function parseNumericFilter(value: string) {
  if (!value.trim()) {
    return undefined;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function formatDate(value?: string | null) {
  if (!value) {
    return '--';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
}

function buildImagePlaceholder(label: string) {
  const safeLabel = encodeURIComponent(label || '暂无图片');
  return `data:image/svg+xml;charset=UTF-8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 320 320'><rect width='320' height='320' rx='28' fill='%23eef3fb'/><text x='160' y='154' text-anchor='middle' font-size='20' fill='%237d6955' font-family='Arial, sans-serif'>暂无图片</text><text x='160' y='186' text-anchor='middle' font-size='14' fill='%23948772' font-family='Arial, sans-serif'>${safeLabel}</text></svg>`;
}

function handleImageError(event: React.SyntheticEvent<HTMLImageElement>, label: string) {
  const img = event.currentTarget;
  img.onerror = null;
  img.src = buildImagePlaceholder(label);
}

function pickPreferredProduct(items: ProductListItem[]) {
  return items.find((item) => (item.main_image_count ?? 0) > 0) ?? items[0] ?? null;
}

function inferQuickFilter(item: ProductListItem) {
  const status = normalizeText(item.status);
  if (status === 'published') {
    return 'published';
  }
  if (status === 'listed') {
    return 'listed';
  }
  if (status === 'optimized') {
    return 'optimized';
  }
  if ((item.total_stock ?? 0) < 20) {
    return 'warning';
  }
  return 'all';
}

function buildLegacyAssets(detail: ProductDetail | undefined, type: 'main' | 'sku'): DisplayAsset[] {
  const source = type === 'main' ? detail?.main_images ?? [] : detail?.sku_images ?? [];
  const assets: DisplayAsset[] = [];
  source.forEach((item, index) => {
      const fallbackSkuName = type === 'sku' ? detail?.skus?.[index]?.sku_name ?? null : null;
      if (typeof item === 'string') {
        assets.push({
          id: `${type}-legacy-${index}`,
          url: resolveAssetUrl(item),
          label: type === 'main' ? `主图 ${index + 1}` : fallbackSkuName ?? `SKU 图 ${index + 1}`,
          kind: type === 'main' ? 'legacy-main' : 'legacy-sku',
          skuName: fallbackSkuName,
        });
        return;
      }
      if (item && typeof item === 'object' && 'url' in item && typeof item.url === 'string') {
        const skuId = 'sku_id' in item && typeof item.sku_id === 'number' ? item.sku_id : null;
        const skuName = 'sku_name' in item && typeof item.sku_name === 'string'
          ? item.sku_name
          : fallbackSkuName;
        assets.push({
          id: `${type}-legacy-${index}`,
          url: resolveAssetUrl(item.url),
          label: type === 'main' ? `主图 ${index + 1}` : skuName ?? (skuId ? `SKU ${skuId}` : `SKU 图 ${index + 1}`),
          kind: type === 'main' ? 'legacy-main' : 'legacy-sku',
          skuId,
          skuName,
        });
      }
    });
  return assets;
}

function buildSkuAssetsFromSkuRows(detail: ProductDetail | undefined): DisplayAsset[] {
  return (detail?.skus ?? [])
    .filter((sku) => typeof sku.image_url === 'string' && Boolean(sku.image_url))
    .map((sku, index) => ({
      id: `sku-row-${sku.id}`,
      url: resolveAssetUrl(sku.image_url),
      label: sku.sku_name ?? `SKU 图 ${index + 1}`,
      kind: 'legacy-sku' as const,
      skuId: sku.id,
      skuName: sku.sku_name,
    }));
}

function buildMediaAssets(detail: ProductDetail | undefined): DisplayAsset[] {
  const seen = new Set<string>();
  const deduped: DisplayAsset[] = [];
  const push = (asset: DisplayAsset) => {
    const skuNameKey = asset.skuName ? normalizeText(asset.skuName) : '';
    const key = asset.kind === 'sku' || asset.kind === 'legacy-sku'
      ? skuNameKey
        ? `sku:${skuNameKey}`
        : asset.assetId != null
          ? `asset:${asset.assetId}`
          : `url:${asset.url}`
      : asset.assetId != null
        ? `asset:${asset.assetId}`
        : `url:${asset.url}`;
    if (!asset.url || seen.has(key)) {
      return;
    }
    seen.add(key);
    deduped.push(asset);
  };

  const normalizeAssetKey = (url: string) => url.trim();

  const rawMainAssets = (detail?.main_media_assets ?? []).map((asset, index) => ({
    id: `main-${asset.id}`,
    assetId: asset.id,
    url: resolveAssetUrl(asset.asset_url),
    label: asset.file_name ?? `主图 ${index + 1}`,
    kind: 'main' as const,
    uploadedAt: asset.uploaded_at,
    deletable: true,
    reorderable: true,
  }));
  const rawLegacyMainAssets = buildLegacyAssets(detail, 'main');
  const rawSkuAssets = (detail?.sku_media_assets ?? []).map((asset, index) => ({
    id: `sku-${asset.id}`,
    assetId: asset.id,
    url: resolveAssetUrl(asset.asset_url),
    label: asset.file_name ?? `SKU 图 ${index + 1}`,
    kind: 'sku' as const,
    skuId: asset.sku_id,
    skuName: asset.sku_name,
    uploadedAt: asset.uploaded_at,
    deletable: true,
    reorderable: true,
  }));
  const rawLegacySkuAssets = buildLegacyAssets(detail, 'sku');
  const rawSkuRowAssets = buildSkuAssetsFromSkuRows(detail);

  const prioritizedSkuAssets = [
    ...rawSkuAssets,
    ...rawLegacySkuAssets,
    ...rawSkuRowAssets,
  ];

  const skuUrlKeys = new Set(
    prioritizedSkuAssets
      .map((asset) => normalizeAssetKey(asset.url))
      .filter(Boolean),
  );

  const mainAssets = [...rawMainAssets, ...rawLegacyMainAssets].filter((asset) => !skuUrlKeys.has(normalizeAssetKey(asset.url)));
  const skuAssets = prioritizedSkuAssets;

  [
    ...mainAssets,
    ...skuAssets,
  ].forEach(push);
  return deduped;
}

function isMainDisplayAsset(asset: DisplayAsset) {
  return asset.kind === 'main' || asset.kind === 'legacy-main';
}

function isSkuDisplayAsset(asset: DisplayAsset) {
  return asset.kind === 'sku' || asset.kind === 'legacy-sku';
}

function buildShopTabs(detail?: ProductDetail, fallbackSites: string[] = DEFAULT_SITE_CODES): ShopTab[] {
  if (!detail) {
    return [{ key: 'global', label: '商品主档' }];
  }

  const tabs: ShopTab[] = [{ key: 'global', label: '商品主档' }];
  const seen = new Set<string>(['global']);

  const pushTab = (siteCode?: string | null, shopCode?: string | null, listing?: SiteListingView) => {
    const safeSite = (siteCode ?? '').trim();
    if (!safeSite) {
      return;
    }
    const safeShop = (shopCode ?? 'default').trim() || 'default';
    const key = `${safeSite}-${safeShop}`;
    if (seen.has(key)) {
      return;
    }
    seen.add(key);
    tabs.push({
      key,
      label: safeShop === 'default' ? safeSite : `${safeSite} / ${safeShop}`,
      siteCode: safeSite,
      shopCode: safeShop,
      listing,
    });
  };

  detail.site_listings.forEach((listing) => {
    pushTab(listing.site, listing.shop_code, listing);
  });
  (detail.published_sites ?? []).forEach((siteCode) => {
    pushTab(siteCode, 'default');
  });
  Object.keys(detail.site_status ?? {}).forEach((siteCode) => {
    pushTab(siteCode, 'default');
  });
  pushTab(detail.profit_summary?.site, 'default');
  fallbackSites.forEach((siteCode) => {
    pushTab(siteCode, 'default');
  });

  return tabs;
}

function pickDefaultShop(detail?: ProductDetail, fallbackSites: string[] = DEFAULT_SITE_CODES) {
  const tabs = buildShopTabs(detail, fallbackSites);
  return tabs[0]?.key ?? 'global';
}

export function ProductManagementPage() {
  const { session } = useAuth();
  const queryClient = useQueryClient();
  const mainImageInputRef = useRef<HTMLInputElement | null>(null);
  const skuImageInputRef = useRef<HTMLInputElement | null>(null);

  const [keyword, setKeyword] = useState('');
  const [serverStatus, setServerStatus] = useState('');
  const [productPage, setProductPage] = useState(1);
  const [selectedProductId, setSelectedProductId] = useState<number | null>(null);
  const [selectedShop, setSelectedShop] = useState('global');
  const [quickFilter, setQuickFilter] = useState<QuickFilterKey>('all');
  const [siteFilter, setSiteFilter] = useState('all');
  const [priceMin, setPriceMin] = useState('');
  const [priceMax, setPriceMax] = useState('');
  const [inventoryWarningOnly, setInventoryWarningOnly] = useState(false);
  const [listingOnly, setListingOnly] = useState(false);
  const [selectedSkuId, setSelectedSkuId] = useState<number | null>(null);
  const [selectedAssetId, setSelectedAssetId] = useState<string>('');
  const [isMediaPreviewOpen, setIsMediaPreviewOpen] = useState(false);
  const [mainImageFile, setMainImageFile] = useState<File | null>(null);
  const [skuImageFile, setSkuImageFile] = useState<File | null>(null);
  const [saveMessage, setSaveMessage] = useState('');
  const [mediaMessage, setMediaMessage] = useState('');
  const [skuNameDrafts, setSkuNameDrafts] = useState<Record<number, string>>({});
  const [editForm, setEditForm] = useState({
    optimized_title: '',
    optimized_description: '',
    category: '',
    brand: '',
    status: 'collected',
  });

  const productsQuery = useQuery({
    queryKey: ['products', 'prototype-redesign', productPage, keyword, serverStatus, quickFilter, siteFilter, priceMin, priceMax, inventoryWarningOnly, listingOnly],
    queryFn: () => fetchProducts({
      page: productPage,
      pageSize: PRODUCT_PAGE_SIZE,
      keyword,
      status: serverStatus,
      quickFilter: quickFilter === 'all' ? undefined : quickFilter,
      siteFilter: siteFilter === 'all' ? undefined : siteFilter,
      priceMin: parseNumericFilter(priceMin),
      priceMax: parseNumericFilter(priceMax),
      inventoryWarningOnly,
      listingOnly,
    }),
    refetchInterval: 30000,
  });

  useEffect(() => {
    setProductPage(1);
  }, [keyword, serverStatus, quickFilter, siteFilter, priceMin, priceMax, inventoryWarningOnly, listingOnly]);

  useEffect(() => {
    if (!selectedProductId && productsQuery.data?.items?.length) {
      const preferred = pickPreferredProduct(productsQuery.data.items);
      setSelectedProductId(preferred?.id ?? null);
    }
  }, [productsQuery.data, selectedProductId]);

  const productDetailQuery = useQuery({
    queryKey: ['product-detail', selectedProductId],
    queryFn: () => fetchProduct(selectedProductId as number),
    enabled: selectedProductId != null,
  });

  const detail = productDetailQuery.data;
  const products = productsQuery.data?.items ?? [];

  useEffect(() => {
    if (!detail) {
      return;
    }
    setEditForm({
      optimized_title: detail.optimized_title ?? detail.title ?? '',
      optimized_description: detail.optimized_description ?? detail.description ?? '',
      category: detail.category ?? '',
      brand: detail.brand ?? '',
      status: detail.status ?? 'collected',
    });
    setSelectedShop(pickDefaultShop(detail, siteOptions));
    setSelectedSkuId((current) => current ?? detail.skus[0]?.id ?? null);
    const firstAsset = buildMediaAssets(detail)[0];
    setSelectedAssetId(firstAsset?.id ?? '');
    setSkuNameDrafts(
      Object.fromEntries(
        detail.skus.map((sku) => [sku.id, sku.shopee_sku_name ?? sku.sku_name ?? '']),
      ),
    );
    setSaveMessage('');
    setMediaMessage('');
  }, [detail]);

  const productMutation = useMutation({
    mutationFn: () => updateProduct(selectedProductId as number, editForm),
    onSuccess: (response) => {
      setSaveMessage(response.message);
      queryClient.setQueryData(['product-detail', selectedProductId], response.product);
      queryClient.invalidateQueries({ queryKey: ['products'] });
      queryClient.invalidateQueries({ queryKey: ['product-detail', selectedProductId] });
    },
    onError: (error) => {
      setSaveMessage(error instanceof Error ? error.message : '商品保存失败');
    },
  });

  const mediaMutation = useMutation({
    mutationFn: async (params: { file: File; usageType: 'main_image' | 'sku_image'; skuId?: number }) => {
      const ticket = await createMediaUploadRequest({
        product_id: selectedProductId as number,
        sku_id: params.skuId,
        file_name: params.file.name,
        content_type: params.file.type || 'image/png',
        size_bytes: params.file.size,
        usage_type: params.usageType,
        media_type: 'image',
      });
      return uploadMediaFile(ticket.ticket.upload_token, params.file);
    },
    onSuccess: (response) => {
      setMediaMessage(response.message);
      setMainImageFile(null);
      setSkuImageFile(null);
      if (mainImageInputRef.current) {
        mainImageInputRef.current.value = '';
      }
      if (skuImageInputRef.current) {
        skuImageInputRef.current.value = '';
      }
      queryClient.invalidateQueries({ queryKey: ['product-detail', selectedProductId] });
      queryClient.invalidateQueries({ queryKey: ['products'] });
    },
    onError: (error) => {
      setMediaMessage(error instanceof Error ? error.message : '图片上传失败');
    },
  });

  const skuMutation = useMutation({
    mutationFn: (params: { skuId: number; shopeeSkuName: string }) =>
      updateProductSku(selectedProductId as number, params.skuId, { shopee_sku_name: params.shopeeSkuName }),
    onSuccess: (response) => {
      setSaveMessage(response.message);
      queryClient.setQueryData(['product-detail', selectedProductId], response.product);
      queryClient.invalidateQueries({ queryKey: ['product-detail', selectedProductId] });
    },
    onError: (error) => {
      setSaveMessage(error instanceof Error ? error.message : 'SKU 规格名称保存失败');
    },
  });

  const sortMutation = useMutation({
    mutationFn: (payload: { usageType: 'main_image' | 'sku_image'; assetIds: number[] }) =>
      sortProductMedia(selectedProductId as number, { usage_type: payload.usageType, asset_ids: payload.assetIds }),
    onSuccess: (response) => {
      setMediaMessage(response.message);
      queryClient.setQueryData(['product-detail', selectedProductId], response.product);
      queryClient.invalidateQueries({ queryKey: ['product-detail', selectedProductId] });
    },
    onError: (error) => {
      setMediaMessage(error instanceof Error ? error.message : '媒体排序失败');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (assetId: number) => deleteProductMedia(selectedProductId as number, assetId),
    onSuccess: (response) => {
      setMediaMessage(response.message);
      queryClient.setQueryData(['product-detail', selectedProductId], response.product);
      queryClient.invalidateQueries({ queryKey: ['product-detail', selectedProductId] });
    },
    onError: (error) => {
      setMediaMessage(error instanceof Error ? error.message : '媒体删除失败');
    },
  });

  const statusOptions = useMemo(
    () => productsQuery.data?.status_options ?? Array.from(new Set(products.map((item) => item.status).filter((item): item is string => Boolean(item)))).sort(),
    [products, productsQuery.data?.status_options],
  );

  const siteOptions = useMemo(() => {
    if (productsQuery.data?.site_options) {
      return Array.from(new Set([...DEFAULT_SITE_CODES, ...productsQuery.data.site_options])).sort();
    }
    const values = new Set<string>();
    DEFAULT_SITE_CODES.forEach((site) => values.add(site));
    products.forEach((item) => {
      (item.published_sites ?? []).forEach((site) => values.add(site));
      Object.keys(item.site_status ?? {}).forEach((site) => values.add(site));
    });
    return Array.from(values).sort();
  }, [products, productsQuery.data?.site_options]);

  useEffect(() => {
    if (selectedProductId && products.some((item) => item.id === selectedProductId)) {
      return;
    }
    const preferred = pickPreferredProduct(products);
    setSelectedProductId(preferred?.id ?? null);
  }, [products, selectedProductId]);

  const quickFilterCounts = useMemo(() => {
    if (productsQuery.data?.quick_filter_counts) {
      return {
        all: productsQuery.data.quick_filter_counts.all ?? 0,
        published: productsQuery.data.quick_filter_counts.published ?? 0,
        listed: productsQuery.data.quick_filter_counts.listed ?? 0,
        optimized: productsQuery.data.quick_filter_counts.optimized ?? 0,
        warning: productsQuery.data.quick_filter_counts.warning ?? 0,
      } satisfies Record<QuickFilterKey, number>;
    }
    return {
      all: products.length,
      published: products.filter((item) => inferQuickFilter(item) === 'published').length,
      listed: products.filter((item) => inferQuickFilter(item) === 'listed').length,
      optimized: products.filter((item) => inferQuickFilter(item) === 'optimized').length,
      warning: products.filter((item) => inferQuickFilter(item) === 'warning').length,
    } satisfies Record<QuickFilterKey, number>;
  }, [products, productsQuery.data?.quick_filter_counts]);

  const shopTabs = useMemo<ShopTab[]>(() => buildShopTabs(detail, siteOptions), [detail, siteOptions]);

  const activeShopTab = useMemo(() => {
    return shopTabs.find((tab) => tab.key === selectedShop) ?? shopTabs[0] ?? { key: 'global', label: '商品主档' };
  }, [selectedShop, shopTabs]);

  useEffect(() => {
    if (!shopTabs.some((tab) => tab.key === selectedShop)) {
      setSelectedShop(shopTabs[0]?.key ?? 'global');
    }
  }, [selectedShop, shopTabs]);

  const isGlobalShop = activeShopTab.key === 'global';
  const mediaAssets = useMemo(() => (isGlobalShop ? buildMediaAssets(detail) : []), [detail, isGlobalShop]);
  const mainMediaAssets = useMemo(() => mediaAssets.filter(isMainDisplayAsset), [mediaAssets]);
  const skuMediaAssets = useMemo(() => mediaAssets.filter(isSkuDisplayAsset), [mediaAssets]);

  useEffect(() => {
    if (!mediaAssets.some((asset) => asset.id === selectedAssetId)) {
      setSelectedAssetId(mediaAssets[0]?.id ?? '');
      setIsMediaPreviewOpen(false);
    }
  }, [mediaAssets, selectedAssetId]);

  useEffect(() => {
    if (!isMediaPreviewOpen) {
      return;
    }

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setIsMediaPreviewOpen(false);
      }
    }

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isMediaPreviewOpen]);

  const selectedAsset = mediaAssets.find((asset) => asset.id === selectedAssetId) ?? mediaAssets[0] ?? null;
  const selectedSku = detail?.skus.find((sku) => sku.id === selectedSkuId) ?? detail?.skus[0] ?? null;

  const skuRows = useMemo(() => {
    if (!detail) {
      return [] as Array<ProductSkuView & { mediaCount: number }>;
    }
    return detail.skus.map((sku) => ({
      ...sku,
      mediaCount: (detail.sku_media_assets ?? []).filter((asset) => asset.sku_id === sku.id).length,
    }));
  }, [detail]);

  const canSave = Boolean(session.authenticated && selectedProductId && editForm.optimized_title.trim());
  const currentListing = activeShopTab.listing;
  const currentSiteCode = activeShopTab.siteCode ?? detail?.profit_summary?.site ?? 'TW';
  const currentSiteStatus = currentListing?.status ?? detail?.site_status?.[currentSiteCode] ?? (activeShopTab.key === 'global' ? detail?.status : 'unconfigured') ?? 'draft';
  const currentSiteTitle = currentListing?.optimized_title ?? detail?.optimized_title ?? detail?.title ?? '未配置站点标题';
  const currentSiteUpdatedAt = currentListing?.updated_at ?? detail?.updated_at;
  const lowStockCount = detail?.logistics_summary?.total_stock ?? 0;
  const estimatedMargin = (() => {
    if (!selectedSku?.price) {
      return null;
    }
    const landed = selectedSku.price * 0.62;
    const profit = selectedSku.price - landed;
    return profit;
  })();

  function resetFilters() {
    setKeyword('');
    setServerStatus('');
    setQuickFilter('all');
    setSiteFilter('all');
    setPriceMin('');
    setPriceMax('');
    setInventoryWarningOnly(false);
    setListingOnly(false);
  }

  function triggerMainUpload() {
    mainImageInputRef.current?.click();
  }

  function triggerSkuUpload() {
    skuImageInputRef.current?.click();
  }

  function openAssetPreview(assetId: string) {
    setSelectedAssetId(assetId);
    setIsMediaPreviewOpen(true);
  }

  function moveAsset(asset: MediaAssetView, direction: -1 | 1) {
    if (!detail || !asset.id) {
      return;
    }
    const list = asset.usage_type === 'sku_image' ? detail.sku_media_assets ?? [] : detail.main_media_assets ?? [];
    const ids = list.map((item) => item.id);
    const currentIndex = ids.indexOf(asset.id);
    const nextIndex = currentIndex + direction;
    if (currentIndex < 0 || nextIndex < 0 || nextIndex >= ids.length) {
      return;
    }
    const nextIds = [...ids];
    [nextIds[currentIndex], nextIds[nextIndex]] = [nextIds[nextIndex], nextIds[currentIndex]];
    sortMutation.mutate({ usageType: asset.usage_type === 'sku_image' ? 'sku_image' : 'main_image', assetIds: nextIds });
  }

  function productCardBadges(item: ProductListItem) {
    const badges = [
      { className: 'listed', label: item.status ?? 'unknown' },
      ...(item.published_sites ?? []).slice(0, 2).map((site) => ({ className: site.toLowerCase(), label: site })),
    ];
    return badges;
  }

  return (
    <div className="shell">
      <WorkspaceSidebar>
        <div className="brand-card">
          <span className="eyebrow">CommerceFlow</span>
          <h1>商品管理</h1>
          <p>按新的后台原型重构商品页交互，保留现有商品、媒体与详情真实接口。</p>
        </div>

        <div className="agent-list-card product-sidebar-summary">
          <div className="section-head compact">
            <h2>页面状态</h2>
            <span>{session.authenticated ? 'online' : 'readonly'}</span>
          </div>
          <div className="summary-strip">
            <span className="status-pill success">真实商品数据</span>
            <span className="status-pill warning">原型交互版</span>
          </div>
          <div className="product-side-meta">
            <span>商品总数 {productsQuery.data?.total ?? 0}</span>
              <span>当前站点 {activeShopTab.label}</span>
            <span>{session.authenticated ? `用户 ${session.user?.display_name ?? session.user?.username}` : '请登录后编辑'}</span>
          </div>
        </div>
      </WorkspaceSidebar>

      <main className="main-panel product-page">
        <section className="product-top-bar table-card">
          <div className="product-top-left">
            <div>
              <span className="eyebrow">Product Workspace</span>
              <h2>商品管理后台</h2>
            </div>
            <label className="shop-dropdown-wrap">
              <span className="shop-dropdown-label">当前站点</span>
              <select className="shop-dropdown" value={activeShopTab.key} onChange={(event) => setSelectedShop(event.target.value)}>
                {shopTabs.map((tab) => (
                  <option key={tab.key} value={tab.key}>{tab.label}</option>
                ))}
              </select>
            </label>
            <span className="exchange-rate">站点 {currentSiteCode} · 最近利润分析 {detail?.profit_summary?.last_analysis_at ? formatDate(detail.profit_summary.last_analysis_at) : '未分析'}</span>
          </div>
          <div className="quick-actions">
            <button className="btn btn-primary" disabled={!canSave || productMutation.isPending} onClick={() => productMutation.mutate()}>
              {productMutation.isPending ? '保存中...' : '保存商品'}
            </button>
            <button className="btn btn-success" disabled={!session.authenticated || mediaMutation.isPending} onClick={triggerMainUpload}>上传主图</button>
            <button className="btn btn-warning" disabled>同步站点</button>
          </div>
        </section>

        <section className="product-search-toolbar table-card">
          <div className="search-row">
            <div className="search-box">
              <span className="search-icon">⌕</span>
              <input
                className="search-input"
                value={keyword}
                onChange={(event) => setKeyword(event.target.value)}
                placeholder="搜索货源ID、商品标题、主货号"
              />
            </div>
            <div className="quick-filters">
              {(Object.keys(QUICK_FILTER_LABELS) as QuickFilterKey[]).map((key) => (
                <button
                  key={key}
                  className={`quick-filter-item ${quickFilter === key ? 'active' : ''}`}
                  onClick={() => setQuickFilter(key)}
                >
                  {QUICK_FILTER_LABELS[key]}
                  <span className="count">{quickFilterCounts[key]}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="filter-row">
            <div className="filter-group">
              <span className="filter-label">商品状态</span>
              <select className="filter-select" value={serverStatus} onChange={(event) => setServerStatus(event.target.value)}>
                <option value="">全部状态</option>
                {statusOptions.map((item) => (
                  <option key={item} value={item}>{item}</option>
                ))}
              </select>
            </div>
            <div className="filter-group">
              <span className="filter-label">店铺范围</span>
              <select className="filter-select" value={siteFilter} onChange={(event) => setSiteFilter(event.target.value)}>
                <option value="all">全部店铺</option>
                {siteOptions.map((item) => (
                  <option key={item} value={item}>{item}</option>
                ))}
              </select>
            </div>
            <div className="filter-group">
              <span className="filter-label">价格区间</span>
              <div className="price-input-group">
                <input className="price-input" value={priceMin} onChange={(event) => setPriceMin(event.target.value)} placeholder="最低" />
                <span className="price-separator">-</span>
                <input className="price-input" value={priceMax} onChange={(event) => setPriceMax(event.target.value)} placeholder="最高" />
              </div>
            </div>
            <label className={`filter-checkbox ${inventoryWarningOnly ? 'checked' : ''}`}>
              <input type="checkbox" checked={inventoryWarningOnly} onChange={(event) => setInventoryWarningOnly(event.target.checked)} />
              <span>仅看库存预警</span>
            </label>
            <label className={`filter-checkbox ${listingOnly ? 'checked' : ''}`}>
              <input type="checkbox" checked={listingOnly} onChange={(event) => setListingOnly(event.target.checked)} />
              <span>仅看已有 Listing</span>
            </label>
            <div className="filter-actions">
              <button className="btn btn-sm" onClick={resetFilters}>重置</button>
            </div>
          </div>
        </section>

        <section className="product-content-area">
          <aside className="product-list-panel table-card">
            <div className="panel-header">
              <div>
                <div className="panel-title">商品列表</div>
                <div className="inline-meta">第 {(productsQuery.data?.page ?? productPage)} 页，当前展示 {products.length} 条，共 {productsQuery.data?.total ?? 0} 条</div>
              </div>
              <span className="status-pill success">实时</span>
            </div>
            {productsQuery.isLoading ? (
              <PageState title="正在加载商品列表" detail="从 products 表读取商品主档和摘要。" />
            ) : productsQuery.isError ? (
              <PageState title="商品列表加载失败" detail={productsQuery.error instanceof Error ? productsQuery.error.message : 'unknown error'} tone="error" />
            ) : products.length === 0 ? (
              <PageState title="没有匹配的商品" detail="调整筛选条件后再试。" />
            ) : (
              <>
                <div className="product-list">
                  {products.map((item) => {
                    const isSelected = item.id === selectedProductId;
                    const preview = item.id === detail?.id ? selectedAsset?.url ?? item.preview_image_url ?? '' : item.preview_image_url ?? '';
                    return (
                      <button key={item.id} className={`product-card ${isSelected ? 'selected' : ''}`} onClick={() => setSelectedProductId(item.id)}>
                        <div className="product-card-header">
                          <div className="product-image">
                            {preview ? <img src={preview} alt={item.title} onError={(event) => handleImageError(event, item.title)} /> : <span>暂无图片</span>}
                          </div>
                          <div className="product-info">
                            <div className="product-title">{item.title}</div>
                            <div className="product-meta">
                              <div>{item.alibaba_product_id ?? '未绑定货源 ID'}</div>
                              <div>{item.product_id_new ?? '未生成主货号'}</div>
                              <div>{toCurrency(item.price_min)} - {toCurrency(item.price_max)}</div>
                            </div>
                          </div>
                        </div>
                        <div className="product-badges">
                          {productCardBadges(item).map((badge, index) => (
                            <span key={`${badge.label}-${index}`} className={`badge badge-${badge.className}`}>{badge.label}</span>
                          ))}
                        </div>
                      </button>
                    );
                  })}
                </div>
                <PaginationControls
                  page={productsQuery.data?.page ?? productPage}
                  hasMore={productsQuery.data?.has_more ?? false}
                  total={productsQuery.data?.total ?? 0}
                  pageSize={PRODUCT_PAGE_SIZE}
                  onPrev={() => setProductPage((value) => Math.max(1, value - 1))}
                  onNext={() => setProductPage((value) => value + 1)}
                  onSelectPage={(page) => setProductPage(page)}
                />
              </>
            )}
          </aside>

          <section className="detail-panel table-card">
            <div className="detail-header">
              <div>
                <div className="detail-title">{detail?.optimized_title ?? detail?.title ?? '请选择商品'}</div>
                <div className="detail-id">{detail?.product_id_new ?? '未选择商品'} · {detail?.alibaba_product_id ?? '--'}</div>
              </div>
              <div className="detail-summary-chips">
                <span className="status-pill success">SKU {detail?.skus.length ?? 0}</span>
                <span className="status-pill warning">Listing {detail?.site_listings.length ?? 0}</span>
              </div>
            </div>

            {productDetailQuery.isLoading ? (
              <PageState title="正在加载商品详情" detail="拉取详情、媒体、SKU 和站点数据。" />
            ) : productDetailQuery.isError ? (
              <PageState title="商品详情加载失败" detail={productDetailQuery.error instanceof Error ? productDetailQuery.error.message : 'unknown error'} tone="error" />
            ) : !detail ? (
              <PageState title="未选择商品" detail="请先在左侧选择一条商品。" />
            ) : (
              <>
                <div className="shop-tabs">
                  {shopTabs.map((tab) => (
                    <button key={tab.key} className={`shop-tab ${selectedShop === tab.key ? 'active' : ''}`} onClick={() => setSelectedShop(tab.key)}>
                      {tab.label}
                    </button>
                  ))}
                </div>

                <div className="detail-content">
                  <section className="detail-section basic-info-section">
                    <div className="section-title">基础信息</div>
                    <div className="detail-form-grid">
                      <label className="detail-form-field detail-form-field-full">
                        <span className="info-label">原商品标题</span>
                        <div className="info-static info-static-textarea">{detail.title ?? '暂无原商品标题'}</div>
                      </label>
                      <label className="detail-form-field detail-form-field-full">
                        <span className="info-label">原简要描述</span>
                        <textarea
                          className="info-value info-textarea info-textarea-readonly"
                          rows={4}
                          value={detail.description ?? '暂无原简要描述'}
                          readOnly
                        />
                      </label>
                      <label className="detail-form-field detail-form-field-full">
                        <span className="info-label">上架标题</span>
                        <input className="info-value" value={editForm.optimized_title} onChange={(event) => setEditForm((prev) => ({ ...prev, optimized_title: event.target.value }))} />
                      </label>
                      <label className="detail-form-field detail-form-field-full">
                        <span className="info-label">上架简要描述</span>
                        <textarea className="info-value info-textarea" rows={4} value={editForm.optimized_description} onChange={(event) => setEditForm((prev) => ({ ...prev, optimized_description: event.target.value }))} />
                      </label>
                      <label className="detail-form-field">
                        <span className="info-label">类目</span>
                        <input className="info-value" value={editForm.category} onChange={(event) => setEditForm((prev) => ({ ...prev, category: event.target.value }))} />
                      </label>
                      <label className="detail-form-field">
                        <span className="info-label">品牌</span>
                        <input className="info-value" value={editForm.brand} onChange={(event) => setEditForm((prev) => ({ ...prev, brand: event.target.value }))} />
                      </label>
                      <label className="detail-form-field">
                        <span className="info-label">商品状态</span>
                        <select className="info-value" value={editForm.status} onChange={(event) => setEditForm((prev) => ({ ...prev, status: event.target.value }))}>
                          {Array.from(new Set([...EDITABLE_STATUSES, ...statusOptions])).map((item) => (
                            <option key={item} value={item}>{item}</option>
                          ))}
                        </select>
                      </label>
                      <div className="detail-form-field readonly-info">
                        <span className="info-label">更新时间</span>
                        <div className="info-static">{formatDate(detail.updated_at)}</div>
                      </div>
                    </div>
                  </section>

                  <section className="detail-section media-gallery-section">
                    <div className="section-title">主图与素材</div>
                    {isGlobalShop ? (
                      <>
                        <div className="media-showcase">
                          <div className="media-groups">
                            <section className="media-group-card">
                              <div className="media-group-header">
                                <div>
                                  <strong>主图</strong>
                                  <span>{mainMediaAssets.length} 张</span>
                                </div>
                                <span className="media-group-hint">点击缩略图预览</span>
                              </div>
                              <div className="image-grid media-group-grid">
                                {mainMediaAssets.length === 0 ? (
                                  <div className="empty-state media-group-empty">当前没有主图。</div>
                                ) : (
                                  mainMediaAssets.map((asset) => (
                                    <button type="button" key={asset.id} className={`image-thumb ${selectedAssetId === asset.id ? 'primary' : ''}`} onClick={() => openAssetPreview(asset.id)}>
                                      <img src={asset.url} alt={asset.label} onError={(event) => handleImageError(event, asset.label)} />
                                      <span>{asset.label}</span>
                                    </button>
                                  ))
                                )}
                              </div>
                            </section>
                            <section className="media-group-card">
                              <div className="media-group-header">
                                <div>
                                  <strong>SKU 图</strong>
                                  <span>{skuMediaAssets.length} 张</span>
                                </div>
                                <span className="media-group-hint">点击缩略图预览</span>
                              </div>
                              <div className="image-grid media-group-grid">
                                {skuMediaAssets.length === 0 ? (
                                  <div className="empty-state media-group-empty">当前没有 SKU 图。</div>
                                ) : (
                                  skuMediaAssets.map((asset) => (
                                    <button type="button" key={asset.id} className={`image-thumb ${selectedAssetId === asset.id ? 'primary' : ''}`} onClick={() => openAssetPreview(asset.id)}>
                                      <img src={asset.url} alt={asset.label} onError={(event) => handleImageError(event, asset.label)} />
                                      <span>{asset.skuName ?? asset.label}</span>
                                    </button>
                                  ))
                                )}
                              </div>
                            </section>
                          </div>
                        </div>
                        <div className="media-toolbar">
                          <input ref={mainImageInputRef} hidden type="file" accept="image/*" onChange={(event) => setMainImageFile(event.target.files?.[0] ?? null)} />
                          <input ref={skuImageInputRef} hidden type="file" accept="image/*" onChange={(event) => setSkuImageFile(event.target.files?.[0] ?? null)} />
                          <button className="btn btn-success" disabled={!session.authenticated} onClick={triggerMainUpload}>选择详情主图</button>
                          <button className="btn btn-primary" disabled={!session.authenticated || !mainImageFile || mediaMutation.isPending} onClick={() => mainImageFile && mediaMutation.mutate({ file: mainImageFile, usageType: 'main_image' })}>上传详情主图</button>
                          <button className="btn btn-success" disabled={!session.authenticated || !selectedSku} onClick={triggerSkuUpload}>选择 SKU 图</button>
                          <button className="btn btn-primary" disabled={!session.authenticated || !selectedSku || !skuImageFile || mediaMutation.isPending} onClick={() => skuImageFile && selectedSku && mediaMutation.mutate({ file: skuImageFile, usageType: 'sku_image', skuId: selectedSku.id })}>上传 SKU 图</button>
                          {selectedAsset?.assetId != null && selectedAsset.kind !== 'legacy-main' && selectedAsset.kind !== 'legacy-sku' ? (
                            <>
                              <button className="btn btn-warning" disabled={!session.authenticated || sortMutation.isPending} onClick={() => {
                                const asset = (selectedAsset.kind === 'sku' ? detail.sku_media_assets : detail.main_media_assets)?.find((item) => item.id === selectedAsset.assetId);
                                if (asset) {
                                  moveAsset(asset, -1);
                                }
                              }}>上移</button>
                              <button className="btn btn-warning" disabled={!session.authenticated || sortMutation.isPending} onClick={() => {
                                const asset = (selectedAsset.kind === 'sku' ? detail.sku_media_assets : detail.main_media_assets)?.find((item) => item.id === selectedAsset.assetId);
                                if (asset) {
                                  moveAsset(asset, 1);
                                }
                              }}>下移</button>
                              <button className="btn btn-danger" disabled={!session.authenticated || deleteMutation.isPending} onClick={() => deleteMutation.mutate(selectedAsset.assetId as number)}>删除图片</button>
                            </>
                          ) : null}
                        </div>
                        {isMediaPreviewOpen && selectedAsset ? (
                          <div className="media-modal-overlay" onClick={() => setIsMediaPreviewOpen(false)}>
                            <div className="media-modal" onClick={(event) => event.stopPropagation()}>
                              <button type="button" className="media-modal-close" onClick={() => setIsMediaPreviewOpen(false)}>关闭</button>
                              <img src={selectedAsset.url} alt={selectedAsset.label} className="media-modal-image" onError={(event) => handleImageError(event, selectedAsset.label)} />
                              <div className="media-modal-meta">
                                <strong>{selectedAsset.label}</strong>
                                <span>{selectedAsset.skuName ?? (selectedAsset.kind === 'main' ? '详情主图' : selectedAsset.kind === 'sku' ? 'SKU 图片' : '历史图片')}</span>
                                <span>{selectedAsset.uploadedAt ? formatDate(selectedAsset.uploadedAt) : '历史数据'}</span>
                              </div>
                            </div>
                          </div>
                        ) : null}
                      </>
                    ) : (
                      <PageState title="站点图片待生成" detail="当前站点页签不展示爬虫抓取的主档素材，待后续站点二次优化后生成。" />
                    )}
                  </section>

                  <section className="detail-section listing-section">
                    <div className="section-title">站点展示信息</div>
                    <div className="shop-listing-card">
                      <div className="listing-title">{currentSiteTitle}</div>
                      <div className="listing-meta-grid">
                        <div>
                          <span className="info-label">站点</span>
                          <div className="info-static">{currentSiteCode}</div>
                        </div>
                        <div>
                          <span className="info-label">店铺</span>
                          <div className="info-static">{activeShopTab.shopCode ?? currentListing?.shop_code ?? 'default'}</div>
                        </div>
                        <div>
                          <span className="info-label">状态</span>
                          <div className="info-static">{currentSiteStatus === 'unconfigured' ? '未配置' : currentSiteStatus}</div>
                        </div>
                        <div>
                          <span className="info-label">最近更新</span>
                          <div className="info-static">{formatDate(currentSiteUpdatedAt)}</div>
                        </div>
                      </div>
                    </div>
                  </section>

                  <section className="detail-section sku-section">
                    <div className="section-title">SKU 规格与库存</div>
                    <div className="sku-table-wrap">
                      <table className="sku-table">
                        <thead>
                          <tr>
                            <th>原规格</th>
                            <th>优化后规格</th>
                            <th>尺寸</th>
                            <th>编码</th>
                            <th>价格</th>
                            <th>库存</th>
                            <th>重量</th>
                            <th>图片</th>
                            <th>操作</th>
                          </tr>
                        </thead>
                        <tbody>
                          {skuRows.map((sku) => (
                            <tr key={sku.id} className={selectedSkuId === sku.id ? 'selected' : ''}>
                              <td>{sku.sku_name ?? `SKU ${sku.id}`}</td>
                              <td>
                                <input
                                  className="info-value"
                                  value={skuNameDrafts[sku.id] ?? sku.shopee_sku_name ?? sku.sku_name ?? ''}
                                  maxLength={30}
                                  onChange={(event) => setSkuNameDrafts((prev) => ({ ...prev, [sku.id]: event.target.value }))}
                                  disabled={!session.authenticated}
                                />
                              </td>
                              <td>{formatDimensions(sku)}</td>
                              <td>{sku.sku_code ?? '--'}</td>
                              <td>{toCurrency(sku.price)}</td>
                              <td>{sku.stock ?? 0}</td>
                              <td>{sku.package_weight ?? 0} g</td>
                              <td>{sku.mediaCount}</td>
                              <td>
                                <button className="edit-btn" onClick={() => setSelectedSkuId(sku.id)}>选中</button>
                                <button
                                  className="edit-btn"
                                  disabled={!session.authenticated || skuMutation.isPending || !(skuNameDrafts[sku.id] ?? '').trim()}
                                  onClick={() => skuMutation.mutate({
                                    skuId: sku.id,
                                    shopeeSkuName: (skuNameDrafts[sku.id] ?? '').trim(),
                                  })}
                                >
                                  保存规格名
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </section>

                  <section className="detail-section profit-card">
                    <div className="section-title">利润分析</div>
                    <div className="profit-row">
                      <div className="profit-item">
                        <span className="label">当前 SKU</span>
                        <span className="value">{selectedSku?.shopee_sku_name ?? selectedSku?.sku_name ?? '未选择'}</span>
                      </div>
                      <div className="profit-item">
                        <span className="label">销售价</span>
                        <span className="value">{toCurrency(selectedSku?.price)}</span>
                      </div>
                      <div className="profit-item">
                        <span className="label">预计利润</span>
                        <span className="value highlight">{estimatedMargin != null ? toCurrency(estimatedMargin) : '--'}</span>
                      </div>
                      <div className="profit-item">
                        <span className="label">总库存</span>
                        <span className="value">{lowStockCount}</span>
                      </div>
                    </div>
                  </section>
                </div>

                <div className="detail-footer">
                  <span className="inline-meta detail-feedback">{saveMessage || mediaMessage || (!session.authenticated ? '请先登录后再执行保存、上传、排序和删除。' : '已按原型完成交互布局，缺少的站点发布接口仍保持禁用。')}</span>
                  <div className="quick-actions">
                    <button className="btn btn-primary" disabled={!canSave || productMutation.isPending} onClick={() => productMutation.mutate()}>
                      {productMutation.isPending ? '保存中...' : '保存变更'}
                    </button>
                    <button className="btn btn-warning" disabled>发布到站点</button>
                  </div>
                </div>
              </>
            )}
          </section>
        </section>
      </main>
    </div>
  );
}