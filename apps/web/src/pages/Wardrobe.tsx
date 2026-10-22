import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowDownToLine,
  ArrowRight,
  CheckCircle2,
  CloudSun,
  FolderArchive,
  Heart,
  Images,
  LayoutGrid,
  Leaf,
  LoaderCircle,
  LogOut,
  Menu,
  Plus,
  RefreshCw,
  Search,
  Shirt,
  SlidersHorizontal,
  Sparkles,
  WashingMachine,
  X,
} from "lucide-react";
import {
  api,
  categories,
  setCsrf,
  type Category,
  type Garment,
  type Job,
  type Session,
  updatePayload,
} from "../lib/api";
import { Brand, Busy, ErrorBox, Dialog } from "../components/ui";
import { AddGarment } from "../features/capture/AddGarment";
import { GarmentCard } from "../features/wardrobe/GarmentCard";
import { GarmentDetail } from "../features/wardrobe/GarmentDetail";
import { JobsPanel } from "../features/jobs/JobsPanel";
import { Outfits } from "../features/outfits/Outfits";

type View =
  "wardrobe" | "favorites" | "laundry" | "archived" | "jobs" | "outfits";
const views: { id: View; title: string; icon: typeof Shirt }[] = [
  { id: "wardrobe", title: "我的衣橱", icon: LayoutGrid },
  { id: "outfits", title: "今日穿搭", icon: CloudSun },
  { id: "favorites", title: "心爱单品", icon: Heart },
  { id: "laundry", title: "洗衣篮", icon: WashingMachine },
  { id: "archived", title: "收纳箱", icon: FolderArchive },
  { id: "jobs", title: "图片处理", icon: Images },
];

export function Wardrobe({ session }: { session: Session }) {
  const client = useQueryClient();
  const [view, setView] = useState<View>(() =>
    window.location.hash === "#outfits" ? "outfits" : "wardrobe",
  );
  const [category, setCategory] = useState<Category | "all">("all");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState("newest");
  const [add, setAdd] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [toast, setToast] = useState("");
  const [error, setError] = useState("");
  const [seeding, setSeeding] = useState(false);
  const [menu, setMenu] = useState(false);
  const previousJobStatuses = useRef(new Map<string, string>());
  const garments = useQuery({
    queryKey: ["garments"],
    queryFn: () => api<Garment[]>("/garments"),
    refetchInterval: 5000,
  });
  const jobs = useQuery({
    queryKey: ["jobs"],
    queryFn: () => api<Job[]>("/jobs"),
    refetchInterval: 5000,
  });
  const health = useQuery({
    queryKey: ["health"],
    queryFn: () => api<{ queue: string; database: string }>("/health"),
    refetchInterval: 15000,
  });
  useEffect(() => {
    const completed = jobs.data?.some(
      (job) =>
        job.status === "succeeded" &&
        previousJobStatuses.current.get(job.id) !== "succeeded",
    );
    if (completed) void client.invalidateQueries({ queryKey: ["garments"] });
    previousJobStatuses.current = new Map(
      jobs.data?.map((job) => [job.id, job.status]),
    );
  }, [jobs.data, client]);
  const items = garments.data ?? [];
  const pending =
    jobs.data?.filter((job) => ["running", "queued"].includes(job.status))
      .length ?? 0;
  const counts = {
    total: items.filter((g) => g.status !== "archived").length,
    available: items.filter((g) => g.status === "available").length,
    laundry: items.filter((g) => g.status === "laundry").length,
    favorites: items.filter((g) => g.favorite && g.status !== "archived")
      .length,
  };
  const active = items.find((item) => item.id === selected);
  const scoped = items.filter((item) =>
    view === "archived"
      ? item.status === "archived"
      : view === "laundry"
        ? item.status === "laundry"
        : view === "favorites"
          ? item.favorite && item.status !== "archived"
          : item.status !== "archived",
  );
  const filtered = scoped
    .filter(
      (item) =>
        (category === "all" || item.category === category) &&
        `${item.name} ${item.color} ${item.material}`
          .toLowerCase()
          .includes(search.toLowerCase()),
    )
    .sort((a, b) =>
      sort === "name"
        ? a.name.localeCompare(b.name, "zh-CN")
        : sort === "worn"
          ? b.wear_count - a.wear_count
          : b.created_at.localeCompare(a.created_at),
    );
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(""), 5000);
      return () => clearTimeout(timer);
    }
  }, [toast]);
  function refresh() {
    void client.invalidateQueries({ queryKey: ["garments"] });
    void client.invalidateQueries({ queryKey: ["jobs"] });
    void client.invalidateQueries({ queryKey: ["recommendations", "latest"] });
  }
  function navigate(next: View) {
    setView(next);
    window.history.replaceState(
      null,
      "",
      next === "outfits" ? "#outfits" : window.location.pathname,
    );
    setCategory("all");
    setSearch("");
    setMenu(false);
  }
  async function seed() {
    setSeeding(true);
    setError("");
    try {
      const result = await api<{ message: string }>("/demo/import", {
        method: "POST",
      });
      refresh();
      setToast(result.message);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSeeding(false);
    }
  }
  async function favorite(item: Garment) {
    try {
      await api(`/garments/${item.id}`, {
        method: "PATCH",
        body: JSON.stringify(updatePayload(item, { favorite: !item.favorite })),
      });
      refresh();
    } catch (e) {
      setError((e as Error).message);
      refresh();
    }
  }
  async function logout() {
    try {
      await api("/auth/logout", { method: "POST" });
      setCsrf("");
      client.removeQueries({
        predicate: (query) => query.queryKey[0] !== "session",
      });
      client.setQueryData(["session"], null);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  const title = views.find((v) => v.id === view)?.title;
  return (
    <div className="app-shell">
      {menu && (
        <button
          className="nav-backdrop"
          aria-label="关闭导航"
          onClick={() => setMenu(false)}
        />
      )}
      <aside className={`sidebar ${menu ? "is-open" : ""}`}>
        <Brand />
        <span className="nav-label">我的空间</span>
        <nav aria-label="主导航">
          {views.map(({ id, title, icon: Icon }) => (
            <button
              key={id}
              className={`nav-item ${view === id ? "active" : ""}`}
              onClick={() => navigate(id)}
              aria-current={view === id ? "page" : undefined}
            >
              <Icon size={19} />
              <span>{title}</span>
              {id === "laundry" && counts.laundry > 0 ? (
                <span className="nav-count">{counts.laundry}</span>
              ) : id === "jobs" && pending > 0 ? (
                <span className="nav-count">{pending}</span>
              ) : null}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="quiet-tip">
            <Leaf size={22} />
            <p>
              穿得更自在，
              <br />
              从了解衣橱开始。
            </p>
            <span>OWN LESS, WEAR MORE.</span>
          </div>
          <button className="account" onClick={logout} aria-label="退出登录">
            <span className="avatar">
              {session.user.display_name.slice(0, 1)}
            </span>
            <span>
              <b>{session.user.display_name}</b>
              <small>独立私人空间</small>
            </span>
            <LogOut size={17} />
          </button>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <button
            className="icon-button mobile-menu"
            aria-label="打开导航"
            onClick={() => setMenu(true)}
          >
            <Menu size={21} />
          </button>
          <div className="breadcrumb">
            我的空间<span>/</span>
            <b>{title}</b>
          </div>
          <span className="connection">
            <i
              className={
                health.isError || health.data?.queue === "unavailable"
                  ? "warn"
                  : ""
              }
            />
            {health.isError
              ? "连接中断"
              : health.data?.queue === "unavailable"
                ? "图片处理暂停"
                : "本机衣橱"}
          </span>
        </header>
        <main>
          <section className="page-heading">
            <div>
              <span className="eyebrow">YOUR EVERYDAY COLLECTION</span>
              <h1>
                {title}
                <span className="heading-dot">.</span>
              </h1>
              <p>
                {view === "wardrobe"
                  ? "让喜欢的衣服，常常出场。"
                  : view === "outfits"
                    ? "按天气选衣，记录自己的穿着感受。"
                    : view === "laundry"
                      ? "洗净之后，再开启下一次出场。"
                      : view === "favorites"
                        ? "那些总想再穿一次的单品。"
                        : view === "archived"
                          ? "暂时收好，等一个合适的季节。"
                          : "照片正在变成井井有条的衣橱。"}
              </p>
            </div>
            <button className="button primary" onClick={() => setAdd(true)}>
              <Plus size={19} />
              添加衣物
            </button>
          </section>
          {error && (
            <div className="inline-error">
              <ErrorBox text={error} />
              <button
                className="icon-button"
                aria-label="关闭错误"
                onClick={() => setError("")}
              >
                <X size={17} />
              </button>
            </div>
          )}
          {view !== "jobs" && view !== "outfits" && (
            <>
              <section className="stats" aria-label="衣橱统计">
                <button onClick={() => navigate("wardrobe")}>
                  <span>衣橱单品</span>
                  <strong>
                    {counts.total.toString().padStart(2, "0")}
                    <small>件</small>
                  </strong>
                  <Shirt />
                </button>
                <button
                  onClick={() => {
                    navigate("wardrobe");
                  }}
                >
                  <span>随时可穿</span>
                  <strong>
                    {counts.available.toString().padStart(2, "0")}
                    <small>件</small>
                  </strong>
                  <CheckCircle2 />
                </button>
                <button onClick={() => navigate("laundry")}>
                  <span>等待洗涤</span>
                  <strong>
                    {counts.laundry.toString().padStart(2, "0")}
                    <small>件</small>
                  </strong>
                  <WashingMachine />
                </button>
                <button onClick={() => navigate("favorites")}>
                  <span>心爱单品</span>
                  <strong>
                    {counts.favorites.toString().padStart(2, "0")}
                    <small>件</small>
                  </strong>
                  <Heart />
                </button>
              </section>
              {view === "wardrobe" && (
                <section className="demo-strip">
                  <span className="demo-icon">
                    <Sparkles size={20} />
                  </span>
                  <div>
                    <b>
                      {items.some((i) => i.is_demo)
                        ? "先用基础款，认识你的新衣橱"
                        : "从四件基础款开始"}
                    </b>
                    <p>导入 AI 生成的演示衣物，试试分类、收藏和洗衣管理。</p>
                  </div>
                  <button
                    className="button quiet"
                    disabled={seeding}
                    onClick={seed}
                  >
                    {seeding ? (
                      <LoaderCircle size={16} className="spin" />
                    ) : (
                      <ArrowDownToLine size={16} />
                    )}
                    导入演示衣物
                  </button>
                </section>
              )}
              <section className="collection">
                <div className="collection-toolbar">
                  <div
                    className="category-tabs"
                    role="group"
                    aria-label="衣物分类"
                  >
                    <button
                      className={category === "all" ? "selected" : ""}
                      onClick={() => setCategory("all")}
                    >
                      全部<span>{scoped.length}</span>
                    </button>
                    {Object.entries(categories).map(([key, label]) => (
                      <button
                        key={key}
                        className={category === key ? "selected" : ""}
                        onClick={() => setCategory(key as Category)}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                  <div className="tools">
                    <label className="search">
                      <Search size={17} />
                      <input
                        aria-label="搜索衣物"
                        placeholder="搜索名称、颜色或材质"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                      />
                    </label>
                    <label className="sort">
                      <SlidersHorizontal size={16} />
                      <select
                        aria-label="排序"
                        value={sort}
                        onChange={(e) => setSort(e.target.value)}
                      >
                        <option value="newest">最近添加</option>
                        <option value="name">按名称</option>
                        <option value="worn">穿着最多</option>
                      </select>
                    </label>
                  </div>
                </div>
                <div className="collection-meta">
                  <span>
                    {filtered.length} 件单品
                    {search ? ` · 搜索「${search}」` : ""}
                  </span>
                  <span>
                    <LayoutGrid size={14} />
                    衣橱视图
                  </span>
                </div>
                {garments.isPending ? (
                  <Busy />
                ) : garments.isError ? (
                  <div className="empty">
                    <ErrorBox text={(garments.error as Error).message} />
                    <button
                      className="button"
                      onClick={() => garments.refetch()}
                    >
                      <RefreshCw size={16} />
                      重新加载
                    </button>
                  </div>
                ) : filtered.length ? (
                  <div className="garment-grid">
                    {filtered.map((item) => (
                      <GarmentCard
                        key={item.id}
                        item={item}
                        onOpen={() => setSelected(item.id)}
                        onFavorite={() => favorite(item)}
                      />
                    ))}
                  </div>
                ) : (
                  <div className="empty">
                    <span className="empty-icon">
                      <Shirt size={32} />
                    </span>
                    <h3>
                      {search || category !== "all"
                        ? "没有找到这件衣服"
                        : view === "laundry"
                          ? "洗衣篮空空，刚刚好"
                          : view === "favorites"
                            ? "把喜欢留在这里"
                            : view === "archived"
                              ? "还没有收纳的衣物"
                              : "衣橱的第一件，会是什么？"}
                    </h3>
                    <p>
                      {search || category !== "all"
                        ? "换一个关键词或分类试试。"
                        : "添加衣物，或导入演示单品开始体验。"}
                    </p>
                    <button
                      className="button"
                      onClick={() =>
                        search || category !== "all"
                          ? (setSearch(""), setCategory("all"))
                          : setAdd(true)
                      }
                    >
                      {search || category !== "all"
                        ? "清除筛选"
                        : "添加第一件衣物"}
                      <ArrowRight size={16} />
                    </button>
                  </div>
                )}
              </section>
            </>
          )}
          {view === "outfits" && (
            <Outfits onOpen={setSelected} notify={setToast} />
          )}
          {view === "jobs" && (
            <JobsPanel
              jobs={jobs.data ?? []}
              error={jobs.error?.message}
              refresh={refresh}
              notify={setToast}
            />
          )}
          <footer className="page-footer">
            <span>给每一件衣服，多一点被穿着的机会。</span>
            <span>IWardrobe · v0.1</span>
          </footer>
        </main>
      </div>
      {add && (
        <Dialog title="添加衣物" onClose={() => setAdd(false)}>
          <AddGarment
            onDone={(message) => {
              refresh();
              setToast(message);
              setAdd(false);
            }}
          />
        </Dialog>
      )}
      {active && (
        <Dialog title="单品详情" onClose={() => setSelected(null)} wide>
          <GarmentDetail
            key={active.id}
            item={active}
            jobs={jobs.data ?? []}
            onChanged={(message) => {
              refresh();
              setToast(message);
            }}
            onClose={() => setSelected(null)}
          />
        </Dialog>
      )}
      {toast && (
        <div className="toast" role="status">
          <CheckCircle2 size={18} />
          {toast}
          <button
            className="icon-button"
            aria-label="关闭提示"
            onClick={() => setToast("")}
          >
            <X size={15} />
          </button>
        </div>
      )}
    </div>
  );
}
