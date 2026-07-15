import { createClient } from "@supabase/supabase-js";

// Public by design — protected by Row Level Security, not secrecy.
// See webapp/supabase/schema.sql for the policies that actually guard this data.
// createClient() throws synchronously on a malformed URL, which would crash
// the whole app (not just the Journal/Training Data tabs) — so this must
// stay a well-formed placeholder URL until real values are filled in.
const SUPABASE_URL = "https://REPLACE_WITH_SUPABASE_PROJECT_REF.supabase.co";
const SUPABASE_ANON_KEY = "REPLACE_WITH_SUPABASE_ANON_KEY";

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
