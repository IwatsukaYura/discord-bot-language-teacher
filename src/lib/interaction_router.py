"""コンポーネント (ボタン) interaction のルーティング。

main.on_interaction に重複していた「custom_id をパース → ハンドラ呼び出し →
失敗時は共通のエラー応答」の連鎖を、ルート定義の登録方式に置き換える。
新しいボタン種別はルートを 1 件追加するだけで済む (OCP)。
"""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import discord

logger = logging.getLogger(__name__)

# custom_id をパースしてハンドラ引数のタプルを返す。対象外の custom_id なら None。
Parser = Callable[[str], tuple | None]
# パース結果を展開して呼ばれる: handle(interaction, *parsed)
Handler = Callable[..., Awaitable[None]]


@dataclass(frozen=True)
class InteractionRoute:
    """1 種類のボタンに対する (パーサ, ハンドラ, エラー文言) の組。"""

    name: str
    parse: Parser
    handle: Handler
    error_message: str


async def route_component_interaction(
    interaction: discord.Interaction,
    custom_id: str,
    routes: tuple[InteractionRoute, ...],
) -> bool:
    """custom_id にマッチした最初のルートへ処理を委譲する。

    ハンドラ内の例外はここで吸収し、未応答ならユーザーにエラー文言を ephemeral で返す
    (Discord interaction は応答必須のため握りつぶさない)。
    マッチしたら True、どのルートにも該当しなければ False。
    """
    for route in routes:
        parsed = route.parse(custom_id)
        if parsed is None:
            continue
        try:
            await route.handle(interaction, *parsed)
        except Exception:
            logger.exception(
                "Failed to handle %s interaction (custom_id=%r)", route.name, custom_id,
            )
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    route.error_message, ephemeral=True,
                )
        return True
    return False
