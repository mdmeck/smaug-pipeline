import { createClient } from "@supabase/supabase-js";

// Public by design — protected by Row Level Security, not secrecy.
// See webapp/supabase/schema.sql for the policies that actually guard this data.
// createClient() throws synchronously on a malformed URL, which would crash
// the whole app (not just the Journal/Training Data tabs) — so this must
// stay a well-formed placeholder URL until real values are filled in.
const SUPABASE_URL = "https://uslbwanjvritktievkxc.supabase.co";
const SUPABASE_ANON_KEY = "sb_publishable_e3RuFiItE8K2lwt5IXkhIw_vowfx3AS";

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
