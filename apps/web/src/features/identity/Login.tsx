import { useState, type FormEvent } from "react";
import { ArrowRight, Leaf, LoaderCircle, CircleHelp } from "lucide-react";
import { api, type Session } from "../../lib/api";
import { Brand, ErrorBox } from "../../components/ui";

export function Login({ onLogin }: { onLogin: (session: Session) => void }) {
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      onLogin(
        await api<Session>("/auth/login", {
          method: "POST",
          body: JSON.stringify({
            username: form.get("username"),
            password: form.get("password"),
          }),
        }),
      );
    } catch (error) {
      setError((error as Error).message);
    } finally {
      setPending(false);
    }
  }
  return (
    <div className="login-page">
      <section className="login-story">
        <Brand />
        <div>
          <span className="eyebrow">LESS GUESSING. MORE YOU.</span>
          <h1>
            每一件衣服，
            <br />
            都有它的日常。
          </h1>
          <p>
            把喜欢的单品收进衣橱。
            <br />
            从一件件衣服开始，找到自己的穿衣节奏。
          </p>
          <div className="story-line">
            <Leaf size={18} /> 好好拥有，也好好穿着
          </div>
        </div>
        <span className="small">IWardrobe · 私人衣橱 / 本机版</span>
      </section>
      <section className="login-form">
        <div className="login-card">
          <span className="eyebrow">WELCOME BACK</span>
          <h2>打开你的衣橱</h2>
          <p className="muted">每个账号拥有独立的衣物和穿着记录。</p>
          <form onSubmit={submit}>
            <label>
              账号
              <input
                name="username"
                autoComplete="username"
                required
                maxLength={80}
                placeholder="输入你的账号"
                autoFocus
              />
            </label>
            <label>
              密码
              <input
                name="password"
                type="password"
                autoComplete="current-password"
                required
                maxLength={200}
                placeholder="输入密码"
              />
            </label>
            {error && <ErrorBox text={error} />}
            <button className="button primary full" disabled={pending}>
              {pending ? <LoaderCircle className="spin" size={18} /> : null}
              进入我的衣橱
              <ArrowRight size={18} />
            </button>
          </form>
          <p className="login-note">
            <CircleHelp size={15} />
            账号由本机管理者创建，首次使用请查看项目运行说明。
          </p>
        </div>
      </section>
    </div>
  );
}
