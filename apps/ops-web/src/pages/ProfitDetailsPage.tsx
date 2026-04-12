import { Fragment, useEffect, useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  fetchProduct,
  fetchProfitAnalysisItems,
  fetchProfitAnalysisSummary,
  fetchProfitInitCandidateSummary,
} from '../api';
import { WorkspaceSidebar } from '../components/WorkspaceSidebar';
import type { ProductDetail, ProfitAnalysisItem } from '../types';

const PROFIT_ITEMS_PAGE_SIZE = 20;

function PageState(props: { title: string; detail: string }) {
  return (
    <div className="state-card">
      <div>
        <strong>{props.title}</strong>
        <p>{props.detail}</p>
      </div>
    </div>
  );
}

function formatTime(value?: string | null) {
  if (!value) return 'N/A';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

function formatPercent(value?: number | null) {
  if (value == null) return 'N/A';
  return `${(value * 100).toFixed(2)}%`;
}

function formatNumeric(value?: number | string | null, suffix = '') {
  if (value == null || value === '') return 'N/A';
  const numeric = Number(value);
  if (Number.isFinite(numeric)) {
    return `${numeric.toFixed(2)}${suffix}`;
  }
  return `${String(value)}${suffix}`;
}

function resolveSiteCurrency(site?: string | null, currency?: string | null) {
  const normalizedCurrency = String(currency || '').trim().toUpperCase();
  if (normalizedCurrency) return normalizedCurrency;
  const normalizedSite = String(site || '').trim().toUpperCase();
  if (normalizedSite === 'PH' || normalizedSite === 'SHOPEE_PH') return 'PHP';
  return 'TWD';
}

function formatLocalSuggestedPrice(item: ProfitAnalysisItem) {
  const localPrice = item.suggested_price_local ?? item.suggested_price_twd;
  return formatNumeric(localPrice, ` ${resolveSiteCurrency(item.site, item.currency)}`);
}

function formatWeight(item: ProfitAnalysisItem) {
  if (item.weight_kg != null) {
    return formatNumeric(item.weight_kg, ' kg');
  }
  if (item.package_weight != null) {
    return formatNumeric(Number(item.package_weight) / 1000, ' kg');
  }
  return 'N/A';
}

function formatDimensions(item: ProfitAnalysisItem) {
  const dimensions = [item.package_length, item.package_width, item.package_height]
    .map((value) => (value == null ? null : Number(value)))
    .filter((value): value is number => Number.isFinite(value));
  if (dimensions.length !== 3) return 'N/A';
  return `${dimensions[0].toFixed(1)} × ${dimensions[1].toFixed(1)} × ${dimensions[2].toFixed(1)} cm`;
}

function requiresTwHomeDelivery(item: ProfitAnalysisItem) {
  if ((item.site ?? 'TW').toUpperCase() !== 'TW') return false;
  return [item.package_length, item.package_width, item.package_height].some((value) => Number(value ?? 0) > 40);
}

function DetailDrawer(props: {
  item: ProfitAnalysisItem | null;
  detail?: ProductDetail;
  isLoading: boolean;
  error: Error | null;
  onClose: () => void;
}) {
  if (!props.item) return null;

  return (
    <div className="profit-drawer-overlay" onClick={props.onClose}>
      <aside className="profit-drawer" onClick={(event) => event.stopPropagation()}>
        <div className="profit-drawer-header">
          <button className="ghost-button profit-drawer-close" onClick={props.onClose}>关闭</button>
          <div>
            <span className="eyebrow">Profit Detail</span>
            <h3 className="profit-drawer-title">{props.item.title ?? props.detail?.optimized_title ?? props.detail?.title ?? '未命名商品'}</h3>
            <div className="profit-drawer-chip-row">
              <span className="status-pill success">{props.item.site ?? 'TW'}</span>
              <span className="status-pill warning">利润率 {formatPercent(props.item.profit_rate ?? null)}</span>
              <span className="status-pill success">编码 {props.item.product_id_new ?? 'N/A'}</span>
            </div>
          </div>
        </div>
        <div className="profit-drawer-scroll">
          {props.isLoading ? (
            <PageState title="正在加载商品详情" detail="读取 products 与 product_skus 明细。" />
          ) : props.error ? (
            <PageState title="商品详情加载失败" detail={props.error.message} />
          ) : (
            <>
              <section className="profit-drawer-section">
                <div className="section-head"><h3>利润摘要</h3><span>{props.item.alibaba_product_id ?? 'N/A'}</span></div>
                <div className="profit-drawer-meta">
                  <div className="profit-drawer-kv"><span className="metric-label">1688商品ID</span><strong>{props.item.alibaba_product_id ?? 'N/A'}</strong></div>
                  <div className="profit-drawer-kv"><span className="metric-label">商品编码</span><strong>{props.item.product_id_new ?? 'N/A'}</strong></div>
                  <div className="profit-drawer-kv"><span className="metric-label">总成本</span><strong>{formatNumeric(props.item.total_cost_cny, ' CNY')}</strong></div>
                  <div className="profit-drawer-kv"><span className="metric-label">建议售价</span><strong>{formatLocalSuggestedPrice(props.item)}</strong></div>
                  <div className="profit-drawer-kv"><span className="metric-label">预计利润</span><strong>{formatNumeric(props.item.estimated_profit_cny, ' CNY')}</strong></div>
                  <div className="profit-drawer-kv"><span className="metric-label">最近分析</span><strong>{formatTime(props.item.updated_at)}</strong></div>
                </div>
              </section>

              <section className="profit-drawer-section">
                <div className="section-head"><h3>商品信息</h3><span>{props.detail?.status ?? 'N/A'}</span></div>
                <div className="profit-drawer-meta">
                  <div className="profit-drawer-kv"><span className="metric-label">优化标题</span><strong>{props.detail?.optimized_title ?? props.detail?.title ?? 'N/A'}</strong></div>
                  <div className="profit-drawer-kv"><span className="metric-label">类目 / 品牌</span><strong>{props.detail?.category ?? 'N/A'} / {props.detail?.brand ?? 'N/A'}</strong></div>
                  <div className="profit-drawer-kv"><span className="metric-label">站点发布数</span><strong>{props.detail?.site_summary?.listing_count ?? 0}</strong></div>
                  <div className="profit-drawer-kv"><span className="metric-label">库存汇总</span><strong>{props.detail?.logistics_summary?.total_stock ?? 0}</strong></div>
                </div>
              </section>

              <section className="profit-drawer-section">
                <div className="section-head"><h3>SKU 明细</h3><span>{props.detail?.skus.length ?? 0}</span></div>
                {!props.detail?.skus.length ? (
                  <PageState title="暂无 SKU 明细" detail="当前商品没有可展示的 SKU 数据。" />
                ) : (
                  <div className="sku-table-wrap">
                    <table className="sku-table">
                      <thead>
                        <tr>
                          <th>SKU 名称</th>
                          <th>SKU 编码</th>
                          <th>价格</th>
                          <th>库存</th>
                          <th>重量</th>
                        </tr>
                      </thead>
                      <tbody>
                        {props.detail.skus.map((sku) => (
                          <tr key={sku.id}>
                            <td>{sku.sku_name ?? '默认SKU'}</td>
                            <td>{sku.sku_code ?? 'N/A'}</td>
                            <td>{formatNumeric(sku.price)}</td>
                            <td>{sku.stock ?? 0}</td>
                            <td>{formatNumeric(sku.package_weight, ' g')}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>

              <section className="profit-drawer-section">
                <div className="section-head"><h3>站点记录</h3><span>{props.detail?.site_listings.length ?? 0}</span></div>
                {props.detail?.site_listings.length ? (
                  <div className="profit-drawer-list">
                    {props.detail.site_listings.map((listing) => (
                      <div key={listing.id} className="record-item static">
                        <strong>{listing.optimized_title ?? '未命名 listing'}</strong>
                        <p>{listing.site ?? 'TW'} · {listing.shop_code ?? 'default'} · {listing.status ?? 'N/A'}</p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <PageState title="暂无站点记录" detail="该商品当前没有站点 listing 记录。" />
                )}
              </section>
            </>
          )}
        </div>
      </aside>
    </div>
  );
}

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
            <button className={`ghost-button page-number-button ${pageNumber === props.page ? 'active' : ''}`} onClick={() => props.onSelectPage(pageNumber)} disabled={pageNumber === props.page}>
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

export function ProfitDetailsPage() {
  const navigate = useNavigate();
  const tableWrapRef = useRef<HTMLDivElement | null>(null);
  const [keyword, setKeyword] = useState('');
  const [site, setSite] = useState('');
  const [profitRateMin, setProfitRateMin] = useState('');
  const [profitRateMax, setProfitRateMax] = useState('');
  const [page, setPage] = useState(1);
  const [selectedProfitRows, setSelectedProfitRows] = useState<Record<number, string>>({});
  const [expandedRowId, setExpandedRowId] = useState<number | null>(null);
  const [expandedProductId, setExpandedProductId] = useState<number | null>(null);
  const [detailItem, setDetailItem] = useState<ProfitAnalysisItem | null>(null);
  const [floatingScrollbarMetrics, setFloatingScrollbarMetrics] = useState({
    visible: false,
    left: 0,
    width: 0,
    maxScrollLeft: 0,
    scrollLeft: 0,
  });

  const summaryQuery = useQuery({
    queryKey: ['profit-analysis-summary', site],
    queryFn: () => fetchProfitAnalysisSummary({ site }),
    refetchInterval: 30000,
  });

  const initCandidateSummaryQuery = useQuery({
    queryKey: ['profit-init-summary', site],
    queryFn: () => fetchProfitInitCandidateSummary({ site }),
    refetchInterval: 30000,
  });

  const itemsQuery = useQuery({
    queryKey: ['profit-analysis-items', page, keyword, site, profitRateMin, profitRateMax],
    queryFn: () => fetchProfitAnalysisItems({
      page,
      pageSize: PROFIT_ITEMS_PAGE_SIZE,
      keyword,
      site,
      profitRateMin: profitRateMin ? Number(profitRateMin) : undefined,
      profitRateMax: profitRateMax ? Number(profitRateMax) : undefined,
    }),
    refetchInterval: 30000,
  });

  const expandedProductDetailQuery = useQuery({
    queryKey: ['profit-expanded-product', expandedProductId],
    queryFn: () => fetchProduct(expandedProductId as number),
    enabled: expandedProductId != null,
  });

  const detailProductQuery = useQuery({
    queryKey: ['profit-detail-product', detailItem?.product_id],
    queryFn: () => fetchProduct(detailItem?.product_id as number),
    enabled: detailItem?.product_id != null,
  });

  const selectedAlibabaIds = useMemo(
    () => Array.from(new Set(Object.values(selectedProfitRows).filter(Boolean))),
    [selectedProfitRows],
  );

  function toggleRow(rowId: number, alibabaId?: string | null) {
    if (!alibabaId) return;
    setSelectedProfitRows((current) => {
      const next = { ...current };
      if (next[rowId]) {
        delete next[rowId];
      } else {
        next[rowId] = alibabaId;
      }
      return next;
    });
  }

  function goToSyncPage() {
    const ids = selectedAlibabaIds.join(',');
    navigate(`/operations/profit/feishu-sync${ids ? `?ids=${encodeURIComponent(ids)}` : ''}`);
  }

  function toggleSkuExpand(item: ProfitAnalysisItem) {
    if (!item.product_id) return;
    if (expandedRowId === item.id) {
      setExpandedRowId(null);
      setExpandedProductId(null);
      return;
    }
    setExpandedRowId(item.id);
    setExpandedProductId(item.product_id);
  }

  function openDetailDrawer(item: ProfitAnalysisItem) {
    setDetailItem(item);
  }

  useEffect(() => {
    const wrap = tableWrapRef.current;
    if (!wrap) return undefined;

    const updateFloatingScrollbar = () => {
      const nextWrap = tableWrapRef.current;
      if (!nextWrap) return;
      const rect = nextWrap.getBoundingClientRect();
      setFloatingScrollbarMetrics({
        visible: nextWrap.scrollWidth > nextWrap.clientWidth + 1,
        left: rect.left,
        width: rect.width,
        maxScrollLeft: Math.max(0, nextWrap.scrollWidth - nextWrap.clientWidth),
        scrollLeft: nextWrap.scrollLeft,
      });
    };

    updateFloatingScrollbar();
    const resizeObserver = new ResizeObserver(updateFloatingScrollbar);
    resizeObserver.observe(wrap);
    window.addEventListener('resize', updateFloatingScrollbar);
    window.addEventListener('scroll', updateFloatingScrollbar, true);

    return () => {
      resizeObserver.disconnect();
      window.removeEventListener('resize', updateFloatingScrollbar);
      window.removeEventListener('scroll', updateFloatingScrollbar, true);
    };
  }, [itemsQuery.data?.items.length, expandedRowId]);

  function syncTableScroll(nextScrollLeft: number) {
    setFloatingScrollbarMetrics((current) =>
      current.scrollLeft === nextScrollLeft ? current : { ...current, scrollLeft: nextScrollLeft },
    );
  }

  function handleFloatingSlider(nextScrollLeft: number) {
    const tableWrap = tableWrapRef.current;
    if (!tableWrap) return;
    tableWrap.scrollLeft = nextScrollLeft;
    syncTableScroll(nextScrollLeft);
  }

  return (
    <div className="shell">
      <WorkspaceSidebar>
        <div className="brand-card">
          <span className="eyebrow">Profit Details</span>
          <h1>利润明细</h1>
          <p>以本地 product_analysis 为准，集中管理商品编码、商品名称、站点与利润率相关的利润明细。</p>
        </div>
      </WorkspaceSidebar>

      <main className="main-panel">
        <section className="hero-panel">
          <div>
            <span className="eyebrow">Profit Analysis</span>
            <h2>利润明细</h2>
            <p>支持按商品编码、商品名称、1688 商品 ID、SKU 关键词搜索，并直接查看商品详情与 SKU 级利润明细。</p>
          </div>
          <div className="hero-status">
            <span className="status-pill success">local-first</span>
            <span className="status-pill warning">searchable</span>
            <span className="status-pill success">paginated</span>
          </div>
        </section>

        <section className="metrics-grid page-metrics-grid profit-metrics-grid">
          <div className="metric-card"><span className="metric-label">分析商品数</span><strong className="metric-value" data-accent="blue">{summaryQuery.data?.total_products ?? 0}</strong></div>
          <div className="metric-card"><span className="metric-label">分析 SKU 数</span><strong className="metric-value" data-accent="green">{summaryQuery.data?.total_skus ?? 0}</strong></div>
          <div className="metric-card"><span className="metric-label">平均利润率</span><strong className="metric-value" data-accent="amber">{formatPercent(summaryQuery.data?.avg_profit_rate ?? null)}</strong></div>
          <div className="metric-card"><span className="metric-label">待初始化商品</span><strong className="metric-value" data-accent="red">{initCandidateSummaryQuery.data?.missing_products ?? 0}</strong></div>
        </section>

        <section className="panel-column profit-details-full">
          <div className="table-card profit-search-card">
            <div className="section-head">
              <h3>搜索筛选</h3>
              <span>按商品信息与利润率过滤</span>
            </div>
            <div className="filters-panel profit-search-filters">
              <input className="filter-input" value={keyword} onChange={(event) => { setKeyword(event.target.value); setPage(1); }} placeholder="搜索商品编码 / 商品名称 / 1688商品ID / SKU" />
              <select className="filter-select" value={site} onChange={(event) => { setSite(event.target.value); setPage(1); }}>
                <option value="">全部站点</option>
                <option value="TW">TW</option>
                <option value="PH">PH</option>
              </select>
              <input className="filter-input" value={profitRateMin} onChange={(event) => { setProfitRateMin(event.target.value); setPage(1); }} placeholder="最低利润率，如 0.1" />
              <input className="filter-input" value={profitRateMax} onChange={(event) => { setProfitRateMax(event.target.value); setPage(1); }} placeholder="最高利润率，如 0.3" />
            </div>
          </div>

          <div className="table-card list-surface">
            <div className="section-head">
              <h3>利润明细列表</h3>
              <span>{itemsQuery.data?.total ?? 0}</span>
            </div>
            <div className="profit-action-row">
              <button className="ghost-button" onClick={goToSyncPage} disabled={selectedAlibabaIds.length === 0}>去飞书同步管理</button>
              <button className="ghost-button" onClick={() => setSelectedProfitRows({})} disabled={selectedAlibabaIds.length === 0}>清空选中</button>
              <span className="inline-meta">已选 {selectedAlibabaIds.length} 个商品，跳转时按商品ID去重</span>
            </div>

            {itemsQuery.isLoading ? (
              <PageState title="正在加载利润明细" detail="从本地 product_analysis 中读取利润结果。" />
            ) : itemsQuery.isError ? (
              <PageState title="利润明细加载失败" detail={itemsQuery.error instanceof Error ? itemsQuery.error.message : 'unknown error'} />
            ) : !(itemsQuery.data?.items?.length) ? (
              <PageState title="暂无利润明细" detail="当前筛选条件下没有利润明细。" />
            ) : (
              <div className="panel-column">
                <div className="profit-table-wrap" ref={tableWrapRef} onScroll={(event) => syncTableScroll(event.currentTarget.scrollLeft)}>
                  <div className="profit-table">
                    <div className="profit-table-header">
                      <span className="profit-table-cell profit-col-select">选中</span>
                      <span className="profit-table-cell profit-col-alibaba">1688商品ID</span>
                      <span className="profit-table-cell profit-col-site">站点</span>
                      <span className="profit-table-cell profit-col-code">商品编码</span>
                      <span className="profit-table-cell profit-col-title">商品名称</span>
                      <span className="profit-table-cell profit-col-sku">SKU</span>
                      <span className="profit-table-cell">采购价CNY</span>
                      <span className="profit-table-cell">建议售价（站点）</span>
                      <span className="profit-table-cell">建议售价CNY</span>
                      <span className="profit-table-cell">利润CNY</span>
                      <span className="profit-table-cell">头程运费CNY</span>
                      <span className="profit-table-cell">货代费CNY</span>
                      <span className="profit-table-cell">SLS藏价CNY</span>
                      <span className="profit-table-cell">平台佣金CNY</span>
                      <span className="profit-table-cell">技术服务费CNY</span>
                      <span className="profit-table-cell">交易服务费CNY</span>
                      <span className="profit-table-cell">重量</span>
                      <span className="profit-table-cell">尺寸</span>
                      <span className="profit-table-cell">操作</span>
                    </div>
                    {itemsQuery.data.items.map((item) => {
                      const selected = Boolean(item.alibaba_product_id && selectedProfitRows[item.id]);
                      const expanded = expandedRowId === item.id;
                      return (
                        <Fragment key={item.id}>
                          <div className={`profit-table-row ${selected ? 'selected' : ''}`}>
                            <div className="profit-table-cell profit-col-select"><input type="checkbox" checked={selected} onChange={() => toggleRow(item.id, item.alibaba_product_id)} disabled={!item.alibaba_product_id} /></div>
                            <div className="profit-table-cell profit-col-alibaba"><strong>{item.alibaba_product_id ?? 'N/A'}</strong></div>
                            <div className="profit-table-cell profit-col-site"><span>{item.site ?? 'TW'}</span></div>
                            <div className="profit-table-cell profit-col-code"><strong>{item.product_id_new ?? 'N/A'}</strong></div>
                            <div className="profit-table-cell profit-col-title">
                              <button className="profit-link-button profit-link-ellipsis" title={item.title ?? '未命名商品'} onClick={() => openDetailDrawer(item)} disabled={!item.product_id}>
                                {item.title ?? '未命名商品'}
                              </button>
                            </div>
                            <div className="profit-table-cell profit-col-sku"><span className="profit-text-wrap">{item.sku_name ?? '默认SKU'}</span></div>
                            <div className="profit-table-cell"><span>{formatNumeric(item.purchase_price_cny, ' CNY')}</span></div>
                            <div className="profit-table-cell"><span>{formatLocalSuggestedPrice(item)}</span></div>
                            <div className="profit-table-cell"><span>{formatNumeric(item.suggested_price_cny, ' CNY')}</span></div>
                            <div className="profit-table-cell"><span>{formatNumeric(item.estimated_profit_cny, ' CNY')}</span></div>
                            <div className="profit-table-cell"><span>{formatNumeric(item.shipping_cn, ' CNY')}</span></div>
                            <div className="profit-table-cell"><span>{formatNumeric(item.agent_fee_cny, ' CNY')}</span></div>
                            <div className="profit-table-cell"><span>{formatNumeric(item.sls_fee_cny, ' CNY')}</span></div>
                            <div className="profit-table-cell"><span>{formatNumeric(item.commission_cny, ' CNY')}</span></div>
                            <div className="profit-table-cell"><span>{formatNumeric(item.service_fee_cny, ' CNY')}</span></div>
                            <div className="profit-table-cell"><span>{formatNumeric(item.transaction_fee_cny, ' CNY')}</span></div>
                            <div className="profit-table-cell"><span>{formatWeight(item)}</span></div>
                            <div className="profit-table-cell profit-dimension-cell">
                              <span className="profit-text-ellipsis" title={formatDimensions(item)}>{formatDimensions(item)}</span>
                              {requiresTwHomeDelivery(item) ? <span className="profit-dimension-warning">TW 超 40cm，需宅配</span> : null}
                            </div>
                            <div className="profit-table-cell">
                              <div className="profit-row-actions">
                                <button className="ghost-button" onClick={() => toggleSkuExpand(item)} disabled={!item.product_id}>
                                  {expanded ? '收起SKU' : '展开SKU'}
                                </button>
                                <button className="ghost-button" onClick={() => openDetailDrawer(item)} disabled={!item.product_id}>详情</button>
                              </div>
                            </div>
                          </div>
                          {expanded ? (
                            <div className="profit-table-expanded">
                              <div className="profit-expand-card">
                                <div className="profit-expand-meta">
                                  <div>
                                    <strong>SKU 级展开</strong>
                                    <p>{item.product_id_new ?? item.alibaba_product_id ?? 'N/A'} · {item.title ?? '未命名商品'}</p>
                                  </div>
                                  <div className="profit-expand-actions">
                                    <button className="ghost-button" onClick={() => openDetailDrawer(item)} disabled={!item.product_id}>打开详情抽屉</button>
                                  </div>
                                </div>
                                {expandedProductDetailQuery.isLoading ? (
                                  <PageState title="正在加载 SKU 明细" detail="读取商品详情中的 SKU 列表。" />
                                ) : expandedProductDetailQuery.isError ? (
                                  <PageState title="SKU 明细加载失败" detail={expandedProductDetailQuery.error instanceof Error ? expandedProductDetailQuery.error.message : 'unknown error'} />
                                ) : !(expandedProductDetailQuery.data?.skus.length) ? (
                                  <PageState title="暂无 SKU 明细" detail="当前商品没有可展示的 SKU 列表。" />
                                ) : (
                                  <div className="sku-table-wrap">
                                    <table className="profit-inline-sku-table">
                                      <thead>
                                        <tr>
                                          <th>SKU 名称</th>
                                          <th>SKU 编码</th>
                                          <th>价格</th>
                                          <th>库存</th>
                                          <th>重量</th>
                                        </tr>
                                      </thead>
                                      <tbody>
                                        {expandedProductDetailQuery.data.skus.map((sku) => (
                                          <tr key={sku.id}>
                                            <td>{sku.sku_name ?? '默认SKU'}</td>
                                            <td>{sku.sku_code ?? 'N/A'}</td>
                                            <td>{formatNumeric(sku.price)}</td>
                                            <td>{sku.stock ?? 0}</td>
                                            <td>{formatNumeric(sku.package_weight, ' g')}</td>
                                          </tr>
                                        ))}
                                      </tbody>
                                    </table>
                                  </div>
                                )}
                              </div>
                            </div>
                          ) : null}
                        </Fragment>
                      );
                    })}
                  </div>
                </div>
                <PaginationControls
                  page={itemsQuery.data.page}
                  hasMore={itemsQuery.data.has_more}
                  total={itemsQuery.data.total}
                  pageSize={itemsQuery.data.page_size}
                  onPrev={() => setPage((current) => Math.max(1, current - 1))}
                  onNext={() => { if (itemsQuery.data.has_more) setPage((current) => current + 1); }}
                  onSelectPage={(value) => setPage(value)}
                />
              </div>
            )}
          </div>
        </section>
      </main>

      <DetailDrawer
        item={detailItem}
        detail={detailProductQuery.data}
        isLoading={detailProductQuery.isLoading}
        error={detailProductQuery.error instanceof Error ? detailProductQuery.error : null}
        onClose={() => setDetailItem(null)}
      />

      {floatingScrollbarMetrics.visible ? (
        <div className="profit-floating-scroll-shell" style={{ left: `${floatingScrollbarMetrics.left}px`, width: `${floatingScrollbarMetrics.width}px` }}>
          <div className="profit-floating-scroll">
            <span className="profit-floating-scroll-label">横向拖动</span>
            <input
              className="profit-floating-slider"
              type="range"
              min={0}
              max={Math.max(1, Math.round(floatingScrollbarMetrics.maxScrollLeft))}
              step={1}
              value={Math.min(Math.round(floatingScrollbarMetrics.scrollLeft), Math.max(1, Math.round(floatingScrollbarMetrics.maxScrollLeft)))}
              onChange={(event) => handleFloatingSlider(Number(event.currentTarget.value))}
            />
          </div>
        </div>
      ) : null}
    </div>
  );
}