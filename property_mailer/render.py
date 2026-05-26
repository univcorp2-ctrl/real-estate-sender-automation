from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .config import Config
from .models import CampaignPlan, Property

JST = timezone(timedelta(hours=9))


def property_fingerprint(prop: Property) -> str:
    stable = "|".join(
        [
            prop.property_id,
            prop.title,
            str(prop.price),
            str(prop.area),
            prop.address,
            prop.status,
            prop.updated_at.isoformat(),
            prop.detail_url,
            prop.brochure_url or "",
        ]
    )
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()


def schedule_time_jst(config: Config) -> str:
    hour, minute = [int(part) for part in config.sender_schedule_time_jst.split(":", 1)]
    now = datetime.now(JST)
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return target.strftime("%Y-%m-%d %H:%M:%S")


def render_campaign(properties: list[Property], config: Config) -> CampaignPlan:
    env = Environment(
        loader=FileSystemLoader(str(Path("templates"))),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    today = datetime.now(JST).strftime("%Y年%m月%d日")
    title = f"最新物件案内 {today}"
    subject = f"【最新物件情報】おすすめ物件 {len(properties)}件のご案内"
    preheader = "最新の物件データから自動チェック済みの情報だけをお届けします。"
    context = {
        "properties": properties,
        "today": today,
        "from_name": config.sender_from_name,
        "reply_to": config.sender_reply_to,
    }
    html = env.get_template("campaign.html.j2").render(**context)
    text = env.get_template("campaign.txt.j2").render(**context)
    return CampaignPlan(
        title=title,
        subject=subject,
        preheader=preheader,
        html=html,
        text=text,
        properties=properties,
        audience_key=config.audience_key,
        fingerprints={prop.property_id: property_fingerprint(prop) for prop in properties},
    )


def render_inquiry_reply(prop: Property, customer_name: str | None) -> tuple[str, str, str]:
    name = customer_name or "お客様"
    subject = f"【資料送付】{prop.title} の物件資料"
    text = (
        f"{name}\n\nお問い合わせありがとうございます。\n"
        f"以下の物件資料をご確認ください。\n\n"
        f"物件名: {prop.title}\n価格: {prop.price:,.0f}円\n所在地: {prop.address}\n詳細URL: {prop.detail_url}\n"
    )
    if prop.brochure_url:
        text += f"資料URL: {prop.brochure_url}\n"
    text += "\nご不明点があればこのメールにご返信ください。"
    html = text.replace("\n", "<br>")
    return subject, text, html
