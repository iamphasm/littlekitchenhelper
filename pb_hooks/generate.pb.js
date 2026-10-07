/// <reference path="../pb_data/types.d.ts" />
// AI proxy: the browser never sees the Anthropic API key.
// POST /api/generate  {prompt: string}  ->  {text, stop_reason}
routerAdd("POST", "/api/generate", (e) => {
  const key = $os.getenv("ANTHROPIC_API_KEY")
  if (!key) throw new ApiError(503, "ai_not_configured", {})

  const body = new DynamicModel({ prompt: "" })
  e.bindBody(body)
  const prompt = String(body.prompt || "")
  if (!prompt.trim()) throw new BadRequestError("prompt required")
  if (prompt.length > 20000) throw new BadRequestError("prompt too long")

  const model = $os.getenv("ANTHROPIC_MODEL") || "claude-sonnet-4-5"
  const res = $http.send({
    url: ($os.getenv("ANTHROPIC_BASE_URL") || "https://api.anthropic.com") + "/v1/messages",
    method: "POST",
    timeout: 120,
    headers: {
      "content-type": "application/json",
      "x-api-key": key,
      "anthropic-version": "2023-06-01",
    },
    body: JSON.stringify({
      model: model,
      max_tokens: 4000,
      messages: [{ role: "user", content: prompt }],
    }),
  })

  if (res.statusCode >= 400) {
    console.log("anthropic error", res.statusCode, toString(res.body).slice(0, 300))
    throw new ApiError(502, "ai_upstream_error", { status: res.statusCode })
  }
  const parts = (res.json && res.json.content) || []
  const text = parts.filter((p) => p.type === "text").map((p) => p.text).join("")
  return e.json(200, { text: text, stop_reason: res.json.stop_reason || "" })
}, $apis.requireAuth())
