/**
 * AI chat model frontend helpers. Extracted from nodeDefinitions/aiModelNodes.ts
 * so they survive the removal of the `nodeDefinitions/` folder. Neither of
 * these is schema data — `AI_MODEL_PROVIDER_MAP` is a static typename →
 * provider-id mapping used for credential / icon routing, and
 * `AI_PROVIDER_OPTIONS` is a UI dropdown list derived from the icon
 * registry. Both are frontend-only.
 */
import { AI_PROVIDER_META } from '../components/icons/AIProviderIcons';

const AI_MODEL_PROVIDERS = [
  'openai',
  'anthropic',
  'gemini',
  'openrouter',
  'llmtr',
  'groq',
  'cerebras',
  'deepseek',
  'kimi',
  'mistral',
  'sarvam',
  // Local-server providers — the chat-model plugins exist
  // (`ollamaChatModel`, `lmstudioChatModel`), so they MUST live in this
  // map for `ParameterRenderer` to derive the provider id from the node
  // type when the schema-implicit `provider` param is absent. Without
  // them the model dropdown stays empty and the runtime falls back to
  // the OpenAI cloud.
  'ollama',
  'lmstudio',
] as const;

/** `<provider>ChatModel` node type → provider id (matches the backend-served
 *  chat model specs). */
export const AI_MODEL_PROVIDER_MAP: Record<string, string> = Object.fromEntries(
  AI_MODEL_PROVIDERS.map(p => [`${p}ChatModel`, p]),
);

/** Option list for `AI Provider` dropdowns (specialized agents, global model
 *  selector). Driven by the icon registry — single source of truth. */
export const AI_PROVIDER_OPTIONS = Object.entries(AI_PROVIDER_META).map(([id, meta]) => ({
  name: meta.label,
  value: id,
}));
