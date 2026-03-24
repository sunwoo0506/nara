export default {
  async fetch(request, env, ctx) {
    if (request.method !== "POST") {
      return new Response("Method Not Allowed", { status: 405 });
    }

    const rawBody = await request.text();
    const timestamp = request.headers.get("X-Slack-Request-Timestamp") ?? "";
    const slackSig = request.headers.get("X-Slack-Signature") ?? "";

    // 리플레이 공격 방지: 5분 초과 요청 거부
    const now = Math.floor(Date.now() / 1000);
    if (Math.abs(now - parseInt(timestamp)) > 300) {
      return new Response("Unauthorized", { status: 401 });
    }

    // HMAC-SHA256 서명 검증
    const encoder = new TextEncoder();
    const key = await crypto.subtle.importKey(
      "raw",
      encoder.encode(env.SLACK_SIGNING_SECRET),
      { name: "HMAC", hash: "SHA-256" },
      false,
      ["sign"]
    );
    const sigBytes = await crypto.subtle.sign(
      "HMAC",
      key,
      encoder.encode(`v0:${timestamp}:${rawBody}`)
    );
    const computed =
      "v0=" +
      Array.from(new Uint8Array(sigBytes))
        .map((b) => b.toString(16).padStart(2, "0"))
        .join("");

    if (computed !== slackSig) {
      return new Response("Unauthorized", { status: 401 });
    }

    // 슬래시 커맨드 본문 파싱
    const params = new URLSearchParams(rawBody);
    const keywords = (params.get("text") ?? "").trim();

    if (!keywords) {
      return Response.json({
        response_type: "ephemeral",
        text: "❌ 키워드를 입력해주세요. 예: `/나라장터 소프트웨어 유지보수`",
      });
    }

    // GitHub Actions workflow_dispatch 트리거 (백그라운드)
    ctx.waitUntil(
      fetch(
        "https://api.github.com/repos/sunwoo0506/nara/actions/workflows/check_bids.yml/dispatches",
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${env.GH_PAT}`,
            Accept: "application/vnd.github.v3+json",
            "Content-Type": "application/json",
            "User-Agent": "nara-slack-bot",
          },
          body: JSON.stringify({ ref: "master", inputs: { keywords } }),
        }
      ).then(async (r) => {
        if (!r.ok) {
          console.error(`GitHub API ${r.status}: ${await r.text()}`);
        }
      })
    );

    return Response.json({
      response_type: "in_channel",
      text: `🔍 \`${keywords}\` 검색 중... 잠시 후 결과를 전송합니다.`,
    });
  },
};
