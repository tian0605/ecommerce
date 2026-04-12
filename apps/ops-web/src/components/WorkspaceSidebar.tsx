import { useEffect, useMemo, useRef, useState, type PropsWithChildren } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { useAuth } from '../auth';

const SIDEBAR_COLLAPSED_STORAGE_KEY = 'ops-workspace-sidebar-collapsed';

type NavNode = {
  key: string;
  label: string;
  to?: string;
  end?: boolean;
  children?: NavNode[];
};

const NAV_TREE: NavNode[] = [
  {
    key: 'operations',
    label: '电商运营',
    children: [
      {
        key: 'products',
        label: '商品中心',
        children: [
          { key: 'products-manage', to: '/products', label: '商品管理' },
        ],
      },
      {
        key: 'auto-listing',
        label: '自动上架',
        children: [
          { key: 'auto-listing-workflow', to: '/operations/auto-listing/workflow', label: '完整工作流上架' },
        ],
      },
      {
        key: 'profit',
        label: '成本利润管理',
        children: [
          { key: 'profit-details', to: '/operations/profit/details', label: '利润明细' },
          { key: 'profit-feishu-sync', to: '/operations/profit/feishu-sync', label: '飞书同步管理' },
        ],
      },
      {
        key: 'config-center',
        label: '配置中心',
        children: [
          { key: 'config-markets', to: '/operations/configs/markets', label: '市场配置' },
          { key: 'config-shipping', to: '/operations/configs/shipping', label: '物流与利润' },
          { key: 'config-content', to: '/operations/configs/content', label: '内容与提示词' },
          { key: 'config-debug', to: '/operations/configs/debug', label: '调试面板' },
          { key: 'config-site-listings', to: '/operations/configs/site-listings', label: '站点 Listing' },
          { key: 'config-system', to: '/operations/configs/system', label: '系统配置' },
        ],
      },
    ],
  },
  {
    key: 'analysis',
    label: '数据分析',
    children: [
      { key: 'dashboard', to: '/', label: '运营总览', end: true },
    ],
  },
];

function nodeHasActivePath(node: NavNode, pathname: string): boolean {
  if (node.to) {
    return node.end ? pathname === node.to : pathname === node.to || pathname.startsWith(`${node.to}/`);
  }
  return Boolean(node.children?.some((child) => nodeHasActivePath(child, pathname)));
}

function collectExpandableKeys(nodes: NavNode[], pathname: string, result: Set<string>) {
  nodes.forEach((node) => {
    if (node.children?.length && nodeHasActivePath(node, pathname)) {
      result.add(node.key);
      collectExpandableKeys(node.children, pathname, result);
    }
  });
}

function WorkspaceNavTree(props: { nodes: NavNode[]; expandedKeys: Set<string>; onToggle: (key: string) => void; depth?: number }) {
  const depth = props.depth ?? 0;
  const location = useLocation();

  return (
    <div className={`workspace-nav-tree depth-${depth}`}>
      {props.nodes.map((node) => {
        if (node.children?.length) {
          const expanded = props.expandedKeys.has(node.key);
          const active = nodeHasActivePath(node, location.pathname);
          return (
            <div key={node.key} className={`workspace-nav-group ${active ? 'active' : ''}`}>
              <button type="button" className={`workspace-nav-group-button ${active ? 'active' : ''}`} onClick={() => props.onToggle(node.key)}>
                <span>{node.label}</span>
                <span className={`workspace-nav-caret ${expanded ? 'expanded' : ''}`}>▾</span>
              </button>
              {expanded ? <WorkspaceNavTree nodes={node.children} expandedKeys={props.expandedKeys} onToggle={props.onToggle} depth={depth + 1} /> : null}
            </div>
          );
        }

        return (
          <NavLink
            key={node.key}
            to={node.to as string}
            end={node.end}
            className={({ isActive }) => `workspace-nav-link workspace-nav-link-depth-${depth} ${isActive ? 'active' : ''}`}
          >
            {node.label}
          </NavLink>
        );
      })}
    </div>
  );
}

export function WorkspaceSidebar(props: PropsWithChildren) {
  const { session, isLoading, login, logout } = useAuth();
  const location = useLocation();
  const sidebarRef = useRef<HTMLElement | null>(null);
  const [username, setUsername] = useState('operator');
  const [password, setPassword] = useState('');
  const [message, setMessage] = useState('');
  const [collapsed, setCollapsed] = useState(() => {
    if (typeof window === 'undefined') return false;
    return window.localStorage.getItem(SIDEBAR_COLLAPSED_STORAGE_KEY) === 'true';
  });
  const defaultExpanded = useMemo(() => {
    const keys = new Set<string>();
    collectExpandableKeys(NAV_TREE, location.pathname, keys);
    return keys;
  }, [location.pathname]);
  const [expandedKeys, setExpandedKeys] = useState<Set<string>>(defaultExpanded);

  useEffect(() => {
    setExpandedKeys((prev) => {
      const next = new Set(prev);
      defaultExpanded.forEach((key) => next.add(key));
      return next;
    });
  }, [defaultExpanded]);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(SIDEBAR_COLLAPSED_STORAGE_KEY, String(collapsed));
    }
  }, [collapsed]);

  useEffect(() => {
    const shell = sidebarRef.current?.closest('.shell');
    if (!shell) return undefined;
    shell.classList.toggle('shell-sidebar-collapsed', collapsed);
    return () => {
      shell.classList.remove('shell-sidebar-collapsed');
    };
  }, [collapsed]);

  const handleToggle = (key: string) => {
    setExpandedKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const handleLogin = async () => {
    try {
      const nextSession = await login({ username, password });
      setPassword('');
      setMessage(nextSession.user ? `已登录：${nextSession.user.display_name}` : '登录失败');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '登录失败');
    }
  };

  const handleLogout = async () => {
    await logout();
    setMessage('已退出登录');
  };

  return (
    <aside ref={sidebarRef} className={`sidebar workspace-sidebar ${collapsed ? 'collapsed' : ''}`}>
      <button
        type="button"
        className="workspace-sidebar-toggle"
        onClick={() => setCollapsed((current) => !current)}
        aria-label={collapsed ? '展开侧边栏' : '隐藏侧边栏'}
        title={collapsed ? '展开侧边栏' : '隐藏侧边栏'}
      >
        <span className={`workspace-sidebar-toggle-icon ${collapsed ? 'collapsed' : ''}`}>▸</span>
      </button>

      <div className="workspace-sidebar-content">
        <div className="workspace-nav-card">
          <span className="eyebrow">CommerceFlow</span>
          <h2>业务模块</h2>
          <WorkspaceNavTree nodes={NAV_TREE} expandedKeys={expandedKeys} onToggle={handleToggle} />
        </div>
        <div className="workspace-nav-card auth-card">
          <span className="eyebrow">Session</span>
          <h2>登录态</h2>
          {session.authenticated && session.user ? (
            <div className="filter-stack">
              <strong>{session.user.display_name}</strong>
              <span className="inline-meta">{session.user.username}</span>
              <span className="inline-meta">{session.user.roles.join(', ')}</span>
              <button className="ghost-button" onClick={handleLogout} disabled={isLoading}>退出登录</button>
            </div>
          ) : (
            <div className="filter-stack">
              <input className="filter-input" value={username} onChange={(event) => setUsername(event.target.value)} placeholder="用户名" />
              <input className="filter-input" type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="密码" />
              <button className="ghost-button" onClick={handleLogin} disabled={isLoading || !username || !password}>
                {isLoading ? '处理中...' : '登录'}
              </button>
            </div>
          )}
          {message ? <span className="inline-meta">{message}</span> : null}
        </div>
        {props.children}
      </div>
    </aside>
  );
}