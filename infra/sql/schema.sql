CREATE TABLE IF NOT EXISTS campaigns (
  id SERIAL PRIMARY KEY,
  platform TEXT,
  campaign_id TEXT,
  name TEXT,
  utm_campaign TEXT,
  created_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS leads (
  id SERIAL PRIMARY KEY,
  source TEXT,
  source_payload JSONB,
  name TEXT,
  phone TEXT,
  email TEXT,
  budget BIGINT,
  intent TEXT,
  lead_score INT DEFAULT 0,
  stage TEXT DEFAULT 'new',
  scheduled_visit TIMESTAMP,
  created_at TIMESTAMP DEFAULT now(),
  updated_at TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS interactions (
  id SERIAL PRIMARY KEY,
  lead_id INT REFERENCES leads(id),
  channel TEXT,
  direction TEXT,
  message TEXT,
  metadata JSONB,
  created_at TIMESTAMP DEFAULT now()
);
