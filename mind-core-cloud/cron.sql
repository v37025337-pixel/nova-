-- Requires Vault secrets:
-- mind_core_project_url
-- mind_core_anon_key
--
-- No credential values belong in source control.

select cron.schedule(
  'mind-core-research-hourly',
  '17 * * * *',
  $$
  select net.http_post(
    url := (select decrypted_secret from vault.decrypted_secrets where name='mind_core_project_url')
           || '/functions/v1/noesis-internet-channel',
    headers := jsonb_build_object(
      'Content-Type','application/json',
      'apikey',(select decrypted_secret from vault.decrypted_secrets where name='mind_core_anon_key'),
      'Authorization','Bearer ' || (select decrypted_secret from vault.decrypted_secrets where name='mind_core_anon_key')
    ),
    body := jsonb_build_object('mode','mind-core','trigger','cron'),
    timeout_milliseconds := 15000
  ) as request_id;
  $$
);
