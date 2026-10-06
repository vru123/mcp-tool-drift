// Preloaded only for the Supabase server. Its search_docs tool fetches a live GraphQL schema from
// supabase.com at tools/list time and pastes it into the tool description. The sandbox cannot reach
// supabase.com, and a live fetch would mix "docs changed" with "release changed". So we answer that one
// request with a FIXED placeholder schema; every other request goes through untouched (and fails offline).
const PLACEHOLDER = 'type Query { searchDocs(query: String!): [Doc] } type Doc { title: String href: String content: String } # PLACEHOLDER: live schema fetched from supabase.com at runtime';
const realFetch = globalThis.fetch;
globalThis.fetch = async (input, init) => {
  const url = typeof input === 'string' ? input : (input && input.url) || String(input);
  if (url.includes('supabase.com/docs/api/graphql')) {
    return new Response(JSON.stringify({ data: { schema: PLACEHOLDER } }), { status: 200, headers: { 'content-type': 'application/json' } });
  }
  return realFetch(input, init);
};
