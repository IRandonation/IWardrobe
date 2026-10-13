import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const accounts = JSON.parse(
  fs.readFileSync(".local/e2e-accounts.json", "utf-8"),
);

test("独立账号的照片建档、洗衣和穿着闭环", async ({
  page,
  context,
}, testInfo) => {
  const account = accounts[testInfo.project.name];
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await page.getByLabel("账号", { exact: true }).fill(account.username);
  await page.getByLabel("密码", { exact: true }).fill(account.password);
  await page.getByRole("button", { name: "进入我的衣橱" }).click();
  await expect(page.getByRole("heading", { name: "我的衣橱." })).toBeVisible();
  await expect(page.locator(".garment-card")).toHaveCount(0);
  await page.getByRole("button", { name: "导入演示衣物" }).click();
  await expect(page.locator(".garment-card")).toHaveCount(4);
  await page.getByRole("button", { name: "导入演示衣物" }).click();
  await expect(page.getByRole("status")).toContainText("不会重复导入");
  await expect(page.locator(".garment-card")).toHaveCount(4);
  await expect
    .poll(
      async () =>
        (await (await context.request.get("/api/jobs")).json()).every(
          (j: { status: string }) => j.status === "succeeded",
        ),
      { timeout: 30000 },
    )
    .toBe(true);
  await page.reload();
  await expect(page.locator(".garment-card img")).toHaveCount(4);
  await expect
    .poll(() =>
      page
        .locator(".garment-card img")
        .evaluateAll((images) =>
          images.every(
            (image) =>
              (image as HTMLImageElement).complete &&
              (image as HTMLImageElement).naturalWidth > 0,
          ),
        ),
    )
    .toBe(true);
  await page
    .getByRole("button", { name: "收藏燕麦色圆领针织衫", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "取消收藏燕麦色圆领针织衫", exact: true }),
  ).toBeVisible();
  await page.getByLabel("搜索衣物").fill("针织");
  await expect(page.locator(".garment-card")).toHaveCount(1);
  await page.getByRole("button", { name: "查看燕麦色圆领针织衫" }).click();
  const dialog = page.getByRole("dialog", { name: "单品详情" });
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "今天穿过" }).click();
  await expect(dialog.getByText("已穿 1 次")).toBeVisible();
  await dialog.getByRole("button", { name: "放入洗衣篮" }).click();
  await expect(dialog.getByText("待洗涤", { exact: true })).toBeVisible();
  await expect(dialog.getByRole("button", { name: "今天穿过" })).toBeDisabled();
  await dialog.getByRole("button", { name: "已经洗净" }).click();
  await expect(dialog.getByText("可穿着", { exact: true })).toBeVisible();
  await dialog
    .getByRole("textbox", { name: "备注", exact: true })
    .fill("浏览器测试：已记录一次穿着并洗净");
  await dialog.getByRole("button", { name: "保存修改" }).click();
  await expect(page.getByRole("status")).toContainText("衣物信息已保存");
  await dialog.getByRole("button", { name: "关闭弹窗" }).click();
  await page.getByLabel("搜索衣物").fill("");
  await expect(page.locator(".garment-card")).toHaveCount(4);
  await page.screenshot({
    path: `.local/screenshots/${testInfo.project.name}-wardrobe.png`,
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.getByRole("button", { name: "添加衣物", exact: true }).click();
  await page
    .getByLabel("选择衣物照片")
    .setInputFiles(path.resolve("fixtures/demo/images/white-sneakers.png"));
  await page.getByRole("button", { name: "添加 1 件衣物" }).click();
  await expect(page.locator(".garment-card")).toHaveCount(5);
  await page.reload();
  await expect(page.locator(".garment-card")).toHaveCount(5);
  const original = await (await context.request.get("/api/garments")).json();
  const other = await context
    .browser()!
    .newContext({ baseURL: "http://127.0.0.1:5173" });
  expect((await other.request.get(original[0].image_url)).status()).toBe(401);
  await other.close();
  if (testInfo.project.name === "mobile")
    await page.getByRole("button", { name: "打开导航" }).click();
  await page.getByRole("button", { name: "退出登录" }).click();
  await expect(
    page.getByRole("heading", { name: "打开你的衣橱" }),
  ).toBeVisible();
  expect((await context.request.get("/api/garments")).status()).toBe(401);
  expect(errors).toEqual([]);
});
