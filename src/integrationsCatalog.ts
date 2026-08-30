import { McpServerDoc, IntegrationToolkit } from './types.js';

export const INTEGRATION_CATEGORIES = [
  { id: 'all', label: 'All Integrations & Plugins', count: 0 },
  { id: 'workspace', label: 'Workspace & Productivity', count: 0 },
  { id: 'dev', label: 'Developer & Engineering', count: 0 },
  { id: 'plugins', label: 'Dev Plugins & Satellites', count: 0 },
  { id: 'ai', label: 'AI & Reasoning', count: 0 },
  { id: 'data', label: 'Databases & Cloud', count: 0 },
  { id: 'web', label: 'Search & Web Scraping', count: 0 },
  { id: 'comm', label: 'Communication & Social', count: 0 },
  { id: 'design', label: 'Design & Media', count: 0 },
];

export const TOOLKITS_LIST: IntegrationToolkit[] = [
  {
    id: 'coding-agent',
    name: 'Autonomous Coding Agent',
    headline: 'Full-cycle engineering toolkit for AI agents',
    description: 'Enables PR reviews, repo search, deep codebase reasoning, issue triage, and error telemetry capture.',
    iconName: 'code',
    badge: 'Popular',
    servers: ['github', 'gitlab', 'sentry', 'sequential-thinking', 'context7', 'deepwiki', 'filesystem'],
    recommendedProfile: 'dev',
  },
  {
    id: 'autonomous-browser',
    name: 'Browser Automation & Scraping',
    headline: 'High-speed headless browser navigation and DOM extraction',
    description: 'Execute Playwright sessions, bypass captchas with Firecrawl, crawl dynamic SPAs, and capture markdown extracts.',
    iconName: 'globe',
    badge: 'Essential',
    servers: ['browser', 'puppeteer', 'firecrawl', 'fetch', 'exa', 'brave-search'],
    recommendedProfile: 'browser',
  },
  {
    id: 'cloud-sre',
    name: 'DevOps & SRE Reliability',
    headline: 'Cloud infra, database operations and production alerts',
    description: 'Direct SQL query executions, Cloudflare edge rule deployments, Redis cache operations, and Sentry crash alerting.',
    iconName: 'cloud',
    badge: 'Production',
    servers: ['cloudflare', 'postgres', 'sqlite', 'upstash', 'sentry', 'kater'],
    recommendedProfile: 'ops',
  },
  {
    id: 'workspace-crm',
    name: 'Team Workspace & CRM Ops',
    headline: 'Automate project planning, issue tracking and docs',
    description: 'Sync Linear issues, update Notion knowledge bases, collaborate on Slack channels, and send transactional emails.',
    iconName: 'briefcase',
    badge: 'Team',
    servers: ['linear', 'notion', 'slack', 'resend', 'figma', 'hubspot', 'gmail'],
    recommendedProfile: 'content',
  },
  {
    id: 'ai-research',
    name: 'Deep AI & Knowledge Graph',
    headline: 'Multi-hop web search, model spaces and long-term memory',
    description: 'Hugging Face model inference, persistent KG entity retrieval, live web grounding, and multi-step reasoning.',
    iconName: 'brain',
    badge: 'AI Core',
    servers: ['huggingface', 'memory', 'exa', 'brave-search', 'sequential-thinking', 'context7', 'perplexity'],
    recommendedProfile: 'research',
  },
];

export const RICH_INTEGRATIONS: McpServerDoc[] = [
  // 1. Gmail
  {
    name: 'gmail',
    displayName: 'Gmail',
    description: 'Read, compose, search, and send emails via Google Workspace & Gmail API.',
    transport: 'http',
    risk: 'high',
    profiles: ['workspace', 'content', 'comm', 'full'],
    category: 'workspace',
    authType: 'oauth',
    verified: true,
    enabled: false,
    env_required: ['GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET'],
    env_configured: false,
    context_cost: 3,
    homepage: 'https://mail.google.com',
    actions: [
      {
        id: 'gmail.send_message',
        name: 'send_message',
        label: 'Send Email Message',
        description: 'Send a new email message with subject, recipients, and HTML or text body.',
        params: [
          { name: 'to', type: 'string', required: true, description: 'Recipient email address' },
          { name: 'subject', type: 'string', required: true, description: 'Email subject line' },
          { name: 'body', type: 'string', required: true, description: 'Message body text or HTML' },
        ],
        exampleInput: { to: 'team@example.com', subject: 'Kater MCP Integration Active', body: 'Automated notification dispatched via Gmail connector.' },
        risk: 'high',
      },
      {
        id: 'gmail.search_threads',
        name: 'search_threads',
        label: 'Search Email Threads',
        description: 'Find emails by query query filters (e.g. from, label, unread).',
        params: [
          { name: 'query', type: 'string', required: true, description: 'Gmail search query string' },
          { name: 'maxResults', type: 'number', required: false, description: 'Maximum threads to return' },
        ],
        exampleInput: { query: 'is:unread label:inbox', maxResults: 10 },
        risk: 'low',
      }
    ],
    triggers: [
      { id: 'gmail.new_email', name: 'new_email', label: 'New Email Received', description: 'Triggers when a new message arrives in user inbox.', eventType: 'email.received' }
    ]
  },

  // 2. Composio
  {
    name: 'composio',
    displayName: 'Composio',
    description: 'Composio core integration framework with 250+ enterprise tools, auth handling, and action grounding.',
    transport: 'stdio',
    risk: 'low',
    profiles: ['core', 'dev', 'full', 'ops'],
    category: 'dev',
    authType: 'api_key',
    verified: true,
    enabled: true,
    activeCount: 1,
    env_required: ['COMPOSIO_API_KEY'],
    env_configured: true,
    context_cost: 2,
    homepage: 'https://composio.dev',
    mcp: {
      command: 'npx',
      args: ['-y', 'composio-core@latest'],
      env_template: { COMPOSIO_API_KEY: '${COMPOSIO_API_KEY}' }
    },
    actions: [
      {
        id: 'composio.execute_action',
        name: 'execute_action',
        label: 'Execute Connected Action',
        description: 'Invoke any Composio catalog action across connected integrations with automated auth management.',
        params: [
          { name: 'action_name', type: 'string', required: true, description: 'Composio action identifier' },
          { name: 'params', type: 'object', required: true, description: 'Action payload arguments' },
        ],
        exampleInput: { action_name: 'GITHUB_CREATE_PULL_REQUEST', params: { title: 'Update release manifest', head: 'patch-1', base: 'main' } },
        risk: 'medium',
      }
    ],
    triggers: []
  },

  // 3. GitHub
  {
    name: 'github',
    displayName: 'GitHub',
    description: 'GitHub repositories, PR review workflows, code searches, CI/CD runs, and issue triage.',
    transport: 'stdio',
    risk: 'high',
    profiles: ['ops', 'code', 'dev', 'full'],
    category: 'dev',
    authType: 'api_key',
    verified: true,
    enabled: true,
    activeCount: 2,
    env_required: ['GITHUB_PERSONAL_ACCESS_TOKEN'],
    env_configured: true,
    context_cost: 4,
    homepage: 'https://github.com',
    mcp: {
      command: 'npx',
      args: ['-y', '@modelcontextprotocol/server-github@2025.4.8'],
      env_template: { GITHUB_PERSONAL_ACCESS_TOKEN: '${GITHUB_PERSONAL_ACCESS_TOKEN}' },
    },
    actions: [
      {
        id: 'github.create_or_update_file',
        name: 'create_or_update_file',
        label: 'Create or Update File',
        description: 'Commit new content or update an existing file in a repository branch.',
        params: [
          { name: 'owner', type: 'string', required: true, description: 'Repository owner or organization' },
          { name: 'repo', type: 'string', required: true, description: 'Repository name' },
          { name: 'path', type: 'string', required: true, description: 'File path in repository' },
          { name: 'content', type: 'string', required: true, description: 'UTF-8 file content' },
          { name: 'message', type: 'string', required: true, description: 'Git commit message' },
        ],
        exampleInput: { owner: 'GroepOnline', repo: 'kater-dev-tools', path: 'README.md', message: 'docs: update integration catalog specs' },
        risk: 'high',
      },
      {
        id: 'github.list_pull_requests',
        name: 'list_pull_requests',
        label: 'List Pull Requests',
        description: 'List and filter open or closed pull requests for a repository.',
        params: [
          { name: 'owner', type: 'string', required: true, description: 'Repository owner' },
          { name: 'repo', type: 'string', required: true, description: 'Repository name' },
          { name: 'state', type: 'string', required: false, description: 'open | closed | all' },
        ],
        exampleInput: { owner: 'GroepOnline', repo: 'kater-dev-tools', state: 'open' },
        risk: 'low',
      }
    ],
    triggers: [
      { id: 'github.pr_opened', name: 'pr_opened', label: 'Pull Request Opened', description: 'Triggers when a PR is created or updated in the target repo.', eventType: 'github.pull_request' }
    ]
  },

  // 4. Google Calendar
  {
    name: 'google-calendar',
    displayName: 'Google Calendar',
    description: 'Schedule meetings, query upcoming events, handle availability, and manage calendar invitations.',
    transport: 'http',
    risk: 'medium',
    profiles: ['workspace', 'content', 'comm'],
    category: 'workspace',
    authType: 'oauth',
    verified: true,
    enabled: false,
    env_required: ['GOOGLE_CALENDAR_CLIENT_ID'],
    env_configured: false,
    context_cost: 3,
    homepage: 'https://calendar.google.com',
    actions: [
      {
        id: 'calendar.create_event',
        name: 'create_event',
        label: 'Create Calendar Event',
        description: 'Schedule a new calendar event with attendees, start/end times, and conference links.',
        params: [
          { name: 'summary', type: 'string', required: true, description: 'Event title' },
          { name: 'startTime', type: 'string', required: true, description: 'ISO 8601 start datetime' },
          { name: 'endTime', type: 'string', required: true, description: 'ISO 8601 end datetime' },
          { name: 'attendees', type: 'array', required: false, description: 'List of attendee email strings' },
        ],
        exampleInput: { summary: 'Kater Architecture Sync', startTime: '2026-09-01T10:00:00Z', endTime: '2026-09-01T10:30:00Z', attendees: ['dev@example.com'] },
        risk: 'medium',
      },
      {
        id: 'calendar.list_events',
        name: 'list_events',
        label: 'List Upcoming Events',
        description: 'Get events between date ranges with location and agenda details.',
        params: [
          { name: 'timeMin', type: 'string', required: false, description: 'ISO 8601 lower bound' },
          { name: 'maxResults', type: 'number', required: false, description: 'Maximum events' },
        ],
        exampleInput: { maxResults: 10 },
        risk: 'low',
      }
    ],
    triggers: []
  },

  // 5. Notion
  {
    name: 'notion',
    displayName: 'Notion',
    description: 'Notion workspaces, databases, structured page blocks, wikis, and project trackers.',
    transport: 'stdio',
    risk: 'medium',
    profiles: ['workspace', 'content', 'dev'],
    category: 'workspace',
    authType: 'api_key',
    verified: true,
    enabled: true,
    activeCount: 1,
    env_required: ['NOTION_API_KEY'],
    env_configured: true,
    context_cost: 4,
    homepage: 'https://notion.so',
    mcp: {
      command: 'npx',
      args: ['-y', '@modelcontextprotocol/server-notion@0.6.0'],
      env_template: { NOTION_API_KEY: '${NOTION_API_KEY}' },
    },
    actions: [
      {
        id: 'notion.query_database',
        name: 'query_database',
        label: 'Query Database',
        description: 'Filter and sort rows within a Notion database with structured property schema.',
        params: [
          { name: 'database_id', type: 'string', required: true, description: 'Notion Database UUID' },
          { name: 'filter', type: 'object', required: false, description: 'Notion property filter criteria' },
        ],
        exampleInput: { database_id: 'db_kater_roadmap_2026', filter: { property: 'Status', select: { equals: 'In Progress' } } },
        risk: 'low',
      },
      {
        id: 'notion.create_page',
        name: 'create_page',
        label: 'Create Page in Notion',
        description: 'Insert a new structured documentation page or database record in Notion.',
        params: [
          { name: 'parent_id', type: 'string', required: true, description: 'Parent page or database ID' },
          { name: 'title', type: 'string', required: true, description: 'Page Title' },
          { name: 'content', type: 'string', required: true, description: 'Markdown formatted body content' },
        ],
        exampleInput: { parent_id: 'page_eng_docs', title: 'Composio MCP Store Architecture', content: '# Overview\nStandardized MCP integration grid.' },
        risk: 'medium',
      }
    ],
    triggers: []
  },

  // 6. Google Sheets
  {
    name: 'google-sheets',
    displayName: 'Google Sheets',
    description: 'Read and append tabular rows, create automated spreadsheets, update cells and run formulas.',
    transport: 'http',
    risk: 'medium',
    profiles: ['workspace', 'content', 'data'],
    category: 'workspace',
    authType: 'oauth',
    verified: true,
    enabled: false,
    env_required: ['GOOGLE_SHEETS_CLIENT_ID'],
    env_configured: false,
    context_cost: 3,
    homepage: 'https://sheets.google.com',
    actions: [
      {
        id: 'sheets.append_rows',
        name: 'append_rows',
        label: 'Append Rows to Sheet',
        description: 'Append an array of tabular values as new rows to a Google Spreadsheet.',
        params: [
          { name: 'spreadsheetId', type: 'string', required: true, description: 'Google Sheet ID' },
          { name: 'range', type: 'string', required: true, description: 'A1 notation target range (e.g. Sheet1!A:E)' },
          { name: 'values', type: 'array', required: true, description: '2D array of row cell values' },
        ],
        exampleInput: { spreadsheetId: '1BxiMVs0XRc5nZy13dfg8j', range: 'Telemetry!A:D', values: [['2026-08-30', 'MCP Server', 'GitHub', 'Success']] },
        risk: 'medium',
      }
    ],
    triggers: []
  },

  // 7. Slack
  {
    name: 'slack',
    displayName: 'Slack',
    description: 'Slack channels, direct messages, incident broadcasting, agent bot responses, and thread tracking.',
    transport: 'stdio',
    risk: 'medium',
    profiles: ['comm', 'content', 'ops', 'dev'],
    category: 'comm',
    authType: 'api_key',
    verified: true,
    enabled: false,
    env_required: ['SLACK_BOT_TOKEN'],
    env_configured: false,
    context_cost: 3,
    homepage: 'https://slack.com',
    mcp: {
      command: 'npx',
      args: ['-y', '@modelcontextprotocol/server-slack@2025.4.8'],
      env_template: { SLACK_BOT_TOKEN: '${SLACK_BOT_TOKEN}' },
    },
    actions: [
      {
        id: 'slack.post_message',
        name: 'post_message',
        label: 'Post Message to Channel',
        description: 'Send a formatted message to a Slack channel with blocks or markdown text.',
        params: [
          { name: 'channel', type: 'string', required: true, description: 'Channel ID (e.g. #engineering, C12345)' },
          { name: 'text', type: 'string', required: true, description: 'Message markdown content' },
        ],
        exampleInput: { channel: '#deployments', text: 'Gateway deployment successful on port 3000.' },
        risk: 'medium',
      }
    ],
    triggers: [
      { id: 'slack.message_posted', name: 'message_posted', label: 'Message Posted in Channel', description: 'Triggers when a message matching keywords is received in a Slack channel.', eventType: 'slack.message' }
    ]
  },

  // 8. Supabase
  {
    name: 'supabase',
    displayName: 'Supabase',
    description: 'Serverless PostgreSQL, Auth, Edge Functions, Storage buckets, and Realtime database changes.',
    transport: 'stdio',
    risk: 'high',
    profiles: ['data', 'dev', 'ops'],
    category: 'data',
    authType: 'api_key',
    verified: true,
    enabled: false,
    env_required: ['SUPABASE_URL', 'SUPABASE_SERVICE_ROLE_KEY'],
    env_configured: false,
    context_cost: 4,
    homepage: 'https://supabase.com',
    mcp: {
      command: 'npx',
      args: ['-y', 'supabase-mcp@latest'],
      env_template: { SUPABASE_URL: '${SUPABASE_URL}', SUPABASE_KEY: '${SUPABASE_SERVICE_ROLE_KEY}' }
    },
    actions: [
      {
        id: 'supabase.execute_sql',
        name: 'execute_sql',
        label: 'Execute SQL Query',
        description: 'Run parameterized SQL query on Supabase PostgreSQL instance.',
        params: [
          { name: 'query', type: 'string', required: true, description: 'SQL SELECT, INSERT, UPDATE query' },
        ],
        exampleInput: { query: 'SELECT count(*) as total_users FROM auth.users;' },
        risk: 'high',
      }
    ],
    triggers: []
  },

  // 9. Outlook
  {
    name: 'outlook',
    displayName: 'Outlook',
    description: 'Microsoft 365 Exchange mail, calendar invites, and corporate mailbox management.',
    transport: 'http',
    risk: 'high',
    profiles: ['workspace', 'comm'],
    category: 'workspace',
    authType: 'oauth',
    verified: true,
    enabled: false,
    env_required: ['AZURE_CLIENT_ID', 'AZURE_TENANT_ID'],
    env_configured: false,
    context_cost: 3,
    homepage: 'https://outlook.office.com',
    actions: [
      {
        id: 'outlook.send_mail',
        name: 'send_mail',
        label: 'Send Email via Outlook',
        description: 'Send email message through Microsoft Graph API.',
        params: [
          { name: 'to', type: 'string', required: true, description: 'Recipient email address' },
          { name: 'subject', type: 'string', required: true, description: 'Email subject' },
          { name: 'body', type: 'string', required: true, description: 'Body text' },
        ],
        exampleInput: { to: 'partner@enterprise.com', subject: 'Kater MCP Integration', body: 'Outlook connection verified.' },
        risk: 'high',
      }
    ],
    triggers: []
  },

  // 10. Perplexity AI
  {
    name: 'perplexity',
    displayName: 'Perplexity AI',
    description: 'Online reasoning and search synthesis powered by Sonar reasoning models and fresh web indexes.',
    transport: 'http',
    risk: 'low',
    profiles: ['ai', 'research', 'web'],
    category: 'ai',
    authType: 'api_key',
    verified: true,
    enabled: false,
    env_required: ['PERPLEXITY_API_KEY'],
    env_configured: false,
    context_cost: 3,
    homepage: 'https://perplexity.ai',
    actions: [
      {
        id: 'perplexity.search_sonar',
        name: 'search_sonar',
        label: 'Sonar Deep Search & Synthesize',
        description: 'Query Perplexity Sonar models with citations and live web knowledge grounding.',
        params: [
          { name: 'query', type: 'string', required: true, description: 'Research query' },
          { name: 'model', type: 'string', required: false, description: 'sonar-pro | sonar-reasoning' },
        ],
        exampleInput: { query: 'Compare MCP stdio vs SSE streaming architecture trade-offs 2026', model: 'sonar-pro' },
        risk: 'low',
      }
    ],
    triggers: []
  },

  // 11. Twitter / X
  {
    name: 'twitter',
    displayName: 'Twitter',
    description: 'Post tweets, monitor user mentions, track hashtag metrics, and retrieve thread conversations on X.',
    transport: 'http',
    risk: 'medium',
    profiles: ['comm', 'content'],
    category: 'comm',
    authType: 'oauth',
    verified: true,
    enabled: false,
    env_required: ['TWITTER_API_KEY', 'TWITTER_API_SECRET'],
    env_configured: false,
    context_cost: 3,
    homepage: 'https://x.com',
    actions: [
      {
        id: 'twitter.post_tweet',
        name: 'post_tweet',
        label: 'Post Tweet on X',
        description: 'Publish a new tweet or thread update.',
        params: [
          { name: 'text', type: 'string', required: true, description: 'Tweet text (max 280 chars)' },
        ],
        exampleInput: { text: 'Kater Dev Tools v1.1.0 is live with Composio Connect Apps & MCP Store.' },
        risk: 'high',
      }
    ],
    triggers: []
  },

  // 12. Google Drive
  {
    name: 'google-drive',
    displayName: 'Google Drive',
    description: 'Upload files, search company drives, download assets, and manage shared folder permissions.',
    transport: 'http',
    risk: 'medium',
    profiles: ['workspace', 'content'],
    category: 'workspace',
    authType: 'oauth',
    verified: true,
    enabled: false,
    env_required: ['GOOGLE_DRIVE_CLIENT_ID'],
    env_configured: false,
    context_cost: 3,
    homepage: 'https://drive.google.com',
    actions: [
      {
        id: 'drive.search_files',
        name: 'search_files',
        label: 'Search Google Drive Files',
        description: 'Find files and documents matching full-text query or mime type filters.',
        params: [
          { name: 'query', type: 'string', required: true, description: 'Drive search query' },
        ],
        exampleInput: { query: "name contains 'Kater Architecture'" },
        risk: 'low',
      }
    ],
    triggers: []
  },

  // 13. Google Docs
  {
    name: 'google-docs',
    displayName: 'Google Docs',
    description: 'Create, format, read and append documents with rich styles and real-time collaboration.',
    transport: 'http',
    risk: 'low',
    profiles: ['workspace', 'content'],
    category: 'workspace',
    authType: 'oauth',
    verified: true,
    enabled: false,
    env_required: ['GOOGLE_DOCS_CLIENT_ID'],
    env_configured: false,
    context_cost: 3,
    homepage: 'https://docs.google.com',
    actions: [
      {
        id: 'docs.create_document',
        name: 'create_document',
        label: 'Create Google Doc',
        description: 'Create a new Google Doc with custom title and initial body.',
        params: [
          { name: 'title', type: 'string', required: true, description: 'Document Title' },
          { name: 'content', type: 'string', required: false, description: 'Initial text' },
        ],
        exampleInput: { title: 'Kater MCP Spec v1.1', content: 'Comprehensive specification of MCP toolkits.' },
        risk: 'low',
      }
    ],
    triggers: []
  },

  // 14. HubSpot
  {
    name: 'hubspot',
    displayName: 'HubSpot',
    description: 'CRM contacts, sales deals, marketing pipelines, company records, and engagement activities.',
    transport: 'http',
    risk: 'medium',
    profiles: ['workspace', 'content'],
    category: 'workspace',
    authType: 'oauth',
    verified: true,
    enabled: false,
    env_required: ['HUBSPOT_ACCESS_TOKEN'],
    env_configured: false,
    context_cost: 3,
    homepage: 'https://hubspot.com',
    actions: [
      {
        id: 'hubspot.create_contact',
        name: 'create_contact',
        label: 'Create CRM Contact',
        description: 'Create or update lead contact with email, firstname, lastname, and company properties.',
        params: [
          { name: 'email', type: 'string', required: true, description: 'Lead email' },
          { name: 'firstname', type: 'string', required: false, description: 'First name' },
          { name: 'company', type: 'string', required: false, description: 'Company name' },
        ],
        exampleInput: { email: 'alex@enterprise.com', firstname: 'Alex', company: 'Acme Corp' },
        risk: 'medium',
      }
    ],
    triggers: []
  },

  // 15. Linear
  {
    name: 'linear',
    displayName: 'Linear',
    description: 'Linear issues, cycles, engineering roadmaps, project milestones, and team backlog management.',
    transport: 'http',
    risk: 'medium',
    profiles: ['content', 'dev', 'ops'],
    category: 'dev',
    authType: 'api_key',
    verified: true,
    enabled: true,
    activeCount: 1,
    env_required: ['LINEAR_API_KEY'],
    env_configured: true,
    context_cost: 3,
    homepage: 'https://linear.app',
    mcp: {
      url: 'https://mcp.linear.app/sse',
      env_template: { LINEAR_API_KEY: '${LINEAR_API_KEY}' },
    },
    actions: [
      {
        id: 'linear.create_issue',
        name: 'create_issue',
        label: 'Create Issue',
        description: 'Create a new issue with title, description, team, priority, and assignees in Linear.',
        params: [
          { name: 'teamId', type: 'string', required: true, description: 'Linear team identifier' },
          { name: 'title', type: 'string', required: true, description: 'Issue summary title' },
          { name: 'description', type: 'string', required: false, description: 'Markdown description' },
          { name: 'priority', type: 'number', required: false, description: '0 (None), 1 (Urgent), 2 (High), 3 (Normal), 4 (Low)' },
        ],
        exampleInput: { teamId: 'ENG', title: 'Audit MCP Server SSE Reconnect Timeouts', priority: 2 },
        risk: 'low',
      }
    ],
    triggers: []
  },

  // 16. Airtable
  {
    name: 'airtable',
    displayName: 'Airtable',
    description: 'Interactive relational databases, customer bases, automated records, and visual grid views.',
    transport: 'http',
    risk: 'medium',
    profiles: ['workspace', 'content', 'data'],
    category: 'workspace',
    authType: 'api_key',
    verified: true,
    enabled: false,
    env_required: ['AIRTABLE_API_KEY'],
    env_configured: false,
    context_cost: 3,
    homepage: 'https://airtable.com',
    actions: [
      {
        id: 'airtable.list_records',
        name: 'list_records',
        label: 'List Airtable Records',
        description: 'Retrieve records from an Airtable base table with field filtering.',
        params: [
          { name: 'baseId', type: 'string', required: true, description: 'Airtable Base ID (app...)' },
          { name: 'tableName', type: 'string', required: true, description: 'Table name' },
        ],
        exampleInput: { baseId: 'app987xyz', tableName: 'Integrations' },
        risk: 'low',
      }
    ],
    triggers: []
  },

  // 17. Code Interpreter
  {
    name: 'code-interpreter',
    displayName: 'Code Interpreter',
    description: 'Secure sandboxed Python & TypeScript code execution environment with data analysis and chart generation.',
    transport: 'stdio',
    risk: 'medium',
    profiles: ['core', 'dev', 'research', 'ai'],
    category: 'dev',
    authType: 'none',
    verified: true,
    enabled: true,
    activeCount: 1,
    env_required: [],
    env_configured: true,
    context_cost: 2,
    homepage: 'https://github.com/modelcontextprotocol/servers',
    actions: [
      {
        id: 'python.execute_code',
        name: 'execute_code',
        label: 'Execute Python Sandbox Code',
        description: 'Run Python 3.12 code snippet, calculate statistics, transform datasets, and return output stdout.',
        params: [
          { name: 'code', type: 'string', required: true, description: 'Executable Python code block' },
        ],
        exampleInput: { code: 'import math\nprint(f"PI: {math.pi}, e: {math.e}")' },
        risk: 'medium',
      }
    ],
    triggers: []
  },

  // 18. SerpApi
  {
    name: 'serpapi',
    displayName: 'SerpApi',
    description: 'Real-time Google, Bing, Yahoo, and Baidu search engine results scraper with structured JSON format.',
    transport: 'http',
    risk: 'low',
    profiles: ['web', 'research'],
    category: 'web',
    authType: 'api_key',
    verified: true,
    enabled: false,
    env_required: ['SERPAPI_API_KEY'],
    env_configured: false,
    context_cost: 2,
    homepage: 'https://serpapi.com',
    actions: [
      {
        id: 'serpapi.google_search',
        name: 'google_search',
        label: 'Google Organic Search',
        description: 'Execute Google search query and return organic results, knowledge graphs, and related questions.',
        params: [
          { name: 'q', type: 'string', required: true, description: 'Search keywords' },
        ],
        exampleInput: { q: 'Model Context Protocol specification 2026' },
        risk: 'low',
      }
    ],
    triggers: []
  },

  // 19. Jira
  {
    name: 'jira',
    displayName: 'Jira',
    description: 'Atlassian Jira enterprise agile sprint boards, issue tracker, velocity charts, and enterprise ticket workflow.',
    transport: 'http',
    risk: 'medium',
    profiles: ['dev', 'workspace', 'ops'],
    category: 'dev',
    authType: 'oauth',
    verified: true,
    enabled: false,
    env_required: ['ATLASSIAN_CLIENT_ID', 'JIRA_DOMAIN'],
    env_configured: false,
    context_cost: 3,
    homepage: 'https://atlassian.com/software/jira',
    actions: [
      {
        id: 'jira.get_issue',
        name: 'get_issue',
        label: 'Get Jira Issue Details',
        description: 'Fetch complete issue details including summary, status, assignee, and comments.',
        params: [
          { name: 'issueKey', type: 'string', required: true, description: 'Issue key (e.g. PROJ-101)' },
        ],
        exampleInput: { issueKey: 'KAT-104' },
        risk: 'low',
      }
    ],
    triggers: []
  },

  // 20. Firecrawl
  {
    name: 'firecrawl',
    displayName: 'Firecrawl',
    description: 'Clean LLM-ready markdown scraping, recursive site crawler, JS-rendered DOM extraction, and search grounding.',
    transport: 'http',
    risk: 'low',
    profiles: ['browser', 'content', 'research', 'dev'],
    category: 'web',
    authType: 'api_key',
    verified: true,
    enabled: true,
    activeCount: 1,
    env_required: ['FIRECRAWL_API_KEY'],
    env_configured: true,
    context_cost: 3,
    homepage: 'https://firecrawl.dev',
    mcp: {
      url: 'https://mcp.firecrawl.dev/sse',
      env_template: { FIRECRAWL_API_KEY: '${FIRECRAWL_API_KEY}' },
    },
    actions: [
      {
        id: 'firecrawl.scrape_url',
        name: 'scrape_url',
        label: 'Scrape URL to Clean Markdown',
        description: 'Convert any web URL into LLM-optimized clean markdown stripping ads, tracking scripts and boilerplate.',
        params: [
          { name: 'url', type: 'string', required: true, description: 'Full HTTPS web address to scrape' },
          { name: 'formats', type: 'array', required: false, description: 'Target formats: markdown | html | rawHtml' },
        ],
        exampleInput: { url: 'https://mcp.so/servers', formats: ['markdown'] },
        risk: 'low',
      }
    ],
    triggers: []
  },

  // 21. Tavily
  {
    name: 'tavily',
    displayName: 'Tavily',
    description: 'AI-agent optimized search engine delivering high-accuracy factual context and answer synthesis.',
    transport: 'http',
    risk: 'low',
    profiles: ['web', 'research', 'ai'],
    category: 'web',
    authType: 'api_key',
    verified: true,
    enabled: false,
    env_required: ['TAVILY_API_KEY'],
    env_configured: false,
    context_cost: 2,
    homepage: 'https://tavily.com',
    actions: [
      {
        id: 'tavily.search',
        name: 'search',
        label: 'Tavily Agent Search',
        description: 'Search web with automated content extraction and AI synthesis summaries.',
        params: [
          { name: 'query', type: 'string', required: true, description: 'Natural language search query' },
          { name: 'search_depth', type: 'string', required: false, description: 'basic | advanced' },
        ],
        exampleInput: { query: 'Best MCP developer tools and gateways 2026', search_depth: 'advanced' },
        risk: 'low',
      }
    ],
    triggers: []
  },

  // 22. YouTube
  {
    name: 'youtube',
    displayName: 'YouTube',
    description: 'Search video transcripts, extract video metadata, fetch channel analytics, and manage playlist items.',
    transport: 'http',
    risk: 'low',
    profiles: ['comm', 'content'],
    category: 'comm',
    authType: 'oauth',
    verified: true,
    enabled: false,
    env_required: ['YOUTUBE_API_KEY'],
    env_configured: false,
    context_cost: 3,
    homepage: 'https://youtube.com',
    actions: [
      {
        id: 'youtube.get_transcript',
        name: 'get_transcript',
        label: 'Fetch Video Transcript',
        description: 'Download full timestamped transcript text from YouTube video ID.',
        params: [
          { name: 'videoId', type: 'string', required: true, description: 'YouTube video ID' },
        ],
        exampleInput: { videoId: 'dQw4w9WgXcQ' },
        risk: 'low',
      }
    ],
    triggers: []
  },

  // 23. Slackbot
  {
    name: 'slackbot',
    displayName: 'Slackbot',
    description: 'Custom Slack agent bot integration with event dispatching, interactive modals, and slash commands.',
    transport: 'http',
    risk: 'medium',
    profiles: ['comm', 'dev'],
    category: 'comm',
    authType: 'api_key',
    verified: true,
    enabled: false,
    env_required: ['SLACKBOT_SECRET'],
    env_configured: false,
    context_cost: 2,
    homepage: 'https://api.slack.com/bot-users',
    actions: [
      {
        id: 'slackbot.dispatch_event',
        name: 'dispatch_event',
        label: 'Dispatch Bot Notification',
        description: 'Send rich interactive card notification through custom Slackbot app.',
        params: [
          { name: 'targetUser', type: 'string', required: true, description: 'Slack User ID or channel' },
          { name: 'content', type: 'string', required: true, description: 'Notification message' },
        ],
        exampleInput: { targetUser: 'U123456', content: 'Your background CI check finished with 0 errors.' },
        risk: 'low',
      }
    ],
    triggers: []
  },

  // 24. Canvas
  {
    name: 'canvas',
    displayName: 'Canvas LMS',
    description: 'Canvas Learning Management System course modules, assignment submissions, grading, and syllabus sync.',
    transport: 'http',
    risk: 'low',
    profiles: ['workspace', 'content'],
    category: 'workspace',
    authType: 'oauth',
    verified: true,
    enabled: false,
    env_required: ['CANVAS_API_TOKEN'],
    env_configured: false,
    context_cost: 3,
    homepage: 'https://instructure.com/canvas',
    actions: [
      {
        id: 'canvas.list_courses',
        name: 'list_courses',
        label: 'List Enrolled Courses',
        description: 'Get list of active student/teacher courses with term metadata.',
        params: [],
        exampleInput: {},
        risk: 'low',
      }
    ],
    triggers: []
  },

  // 25. Figma
  {
    name: 'figma',
    displayName: 'Figma',
    description: 'Figma dev mode design tokens, component inspect, vector assets and layout hierarchies.',
    transport: 'stdio',
    risk: 'medium',
    profiles: ['image', 'content', 'dev', 'design'],
    category: 'design',
    authType: 'api_key',
    verified: true,
    enabled: false,
    env_required: ['FIGMA_API_KEY'],
    env_configured: false,
    context_cost: 3,
    homepage: 'https://figma.com',
    mcp: {
      command: 'npx',
      args: ['-y', 'figma-developer-mcp@0.13.2'],
      env_template: { FIGMA_API_KEY: '${FIGMA_API_KEY}' },
    },
    actions: [
      {
        id: 'figma.get_file',
        name: 'get_file',
        label: 'Get Figma File Structure',
        description: 'Read document tree, components, frames, and typography styles.',
        params: [{ name: 'fileKey', type: 'string', required: true, description: 'Figma file key from URL' }],
        exampleInput: { fileKey: 'abc123xyz' },
        risk: 'low',
      }
    ],
    triggers: []
  },

  // 26. Resend
  {
    name: 'resend',
    displayName: 'Resend',
    description: 'Developer-first transactional email dispatch, domain verification, and webhook notifications.',
    transport: 'stdio',
    risk: 'high',
    profiles: ['email', 'content', 'comm'],
    category: 'comm',
    authType: 'api_key',
    verified: true,
    enabled: false,
    env_required: ['RESEND_API_KEY'],
    env_configured: false,
    context_cost: 5,
    homepage: 'https://resend.com',
    mcp: {
      command: 'npx',
      args: ['-y', 'resend-mcp@2.9.0'],
      env_template: { RESEND_API_KEY: '${RESEND_API_KEY}' },
    },
    actions: [
      {
        id: 'resend.send_email',
        name: 'send_email',
        label: 'Send Email',
        description: 'Dispatch transactional HTML or plaintext email via Resend API.',
        params: [
          { name: 'to', type: 'string', required: true, description: 'Recipient email address' },
          { name: 'subject', type: 'string', required: true, description: 'Email subject line' },
          { name: 'html', type: 'string', required: true, description: 'HTML content' },
        ],
        exampleInput: { to: 'developer@example.com', subject: 'Your Kater Gateway Deployment is Ready', html: '<p>All systems operational.</p>' },
        risk: 'high',
      }
    ],
    triggers: []
  },

  // 27. Sentry
  {
    name: 'sentry',
    displayName: 'Sentry',
    description: 'Real-time crash reporting, issue aggregation, stack traces, and release telemetry.',
    transport: 'stdio',
    risk: 'medium',
    profiles: ['dev', 'ops', 'full'],
    category: 'dev',
    authType: 'api_key',
    verified: true,
    enabled: true,
    activeCount: 1,
    env_required: ['SENTRY_AUTH_TOKEN'],
    env_configured: true,
    context_cost: 3,
    homepage: 'https://sentry.io',
    mcp: {
      command: 'npx',
      args: ['-y', '@modelcontextprotocol/server-sentry@0.6.2'],
      env_template: { SENTRY_AUTH_TOKEN: '${SENTRY_AUTH_TOKEN}' },
    },
    actions: [
      {
        id: 'sentry.list_issues',
        name: 'list_issues',
        label: 'List Sentry Issues',
        description: 'Fetch unresolved errors and crash reports filtered by project and environment.',
        params: [
          { name: 'organization_slug', type: 'string', required: true, description: 'Sentry organization name' },
          { name: 'project_slug', type: 'string', required: true, description: 'Sentry project slug' },
        ],
        exampleInput: { organization_slug: 'kater-dev', project_slug: 'gateway' },
        risk: 'low',
      }
    ],
    triggers: []
  },

  // 28. PostgreSQL
  {
    name: 'postgres',
    displayName: 'PostgreSQL',
    description: 'PostgreSQL database direct inspection, schema introspection, and analytical query execution.',
    transport: 'stdio',
    risk: 'high',
    profiles: ['data', 'ops', 'dev'],
    category: 'data',
    authType: 'custom',
    verified: true,
    enabled: false,
    env_required: ['DATABASE_URL'],
    env_configured: false,
    context_cost: 4,
    homepage: 'https://postgresql.org',
    mcp: {
      command: 'npx',
      args: ['-y', '@modelcontextprotocol/server-postgres@0.6.2', '${DATABASE_URL}'],
      env_template: { DATABASE_URL: '${DATABASE_URL}' },
    },
    actions: [
      {
        id: 'postgres.query',
        name: 'query',
        label: 'Execute SQL Query',
        description: 'Execute read-only or transactional query on PostgreSQL database.',
        params: [{ name: 'sql', type: 'string', required: true, description: 'SQL statement to execute' }],
        exampleInput: { sql: 'SELECT table_name FROM information_schema.tables WHERE table_schema = "public";' },
        risk: 'high',
      }
    ],
    triggers: []
  },

  // 29. Cloudflare
  {
    name: 'cloudflare',
    displayName: 'Cloudflare',
    description: 'Cloudflare edge workers, DNS zones, KV stores, D1 database, and security rules.',
    transport: 'http',
    risk: 'high',
    profiles: ['ops', 'data', 'dev'],
    category: 'data',
    authType: 'api_key',
    verified: true,
    enabled: false,
    env_required: ['CLOUDFLARE_API_TOKEN'],
    env_configured: false,
    context_cost: 4,
    homepage: 'https://cloudflare.com',
    mcp: {
      url: 'https://mcp.cloudflare.com/sse',
      env_template: { CLOUDFLARE_API_TOKEN: '${CLOUDFLARE_API_TOKEN}' },
    },
    actions: [
      {
        id: 'cloudflare.list_zones',
        name: 'list_zones',
        label: 'List DNS Zones',
        description: 'Retrieve all managed domains and active edge DNS routing rules.',
        params: [],
        exampleInput: {},
        risk: 'low',
      }
    ],
    triggers: []
  },

  // 30. Brave Search
  {
    name: 'brave-search',
    displayName: 'Brave Search',
    description: 'Privacy-focused independent web indexing and search grounding for AI agent queries.',
    transport: 'stdio',
    risk: 'low',
    profiles: ['research', 'web', 'dev'],
    category: 'web',
    authType: 'api_key',
    verified: true,
    enabled: true,
    activeCount: 1,
    env_required: ['BRAVE_API_KEY'],
    env_configured: true,
    context_cost: 2,
    homepage: 'https://brave.com/search',
    mcp: {
      command: 'npx',
      args: ['-y', '@modelcontextprotocol/server-brave-search@0.6.2'],
      env_template: { BRAVE_API_KEY: '${BRAVE_API_KEY}' },
    },
    actions: [
      {
        id: 'brave.search',
        name: 'search',
        label: 'Web Search',
        description: 'Query Brave web search index for query keywords.',
        params: [{ name: 'query', type: 'string', required: true, description: 'Search terms' }],
        exampleInput: { query: 'Model Context Protocol toolkits 2026' },
        risk: 'low',
      }
    ],
    triggers: []
  },

  // 31. Exa
  {
    name: 'exa',
    displayName: 'Exa AI',
    description: 'Neural web search engine designed specifically for autonomous agent tool grounding.',
    transport: 'http',
    risk: 'medium',
    profiles: ['research', 'web', 'dev'],
    category: 'ai',
    authType: 'api_key',
    verified: true,
    enabled: true,
    activeCount: 1,
    env_required: ['EXA_API_KEY'],
    env_configured: true,
    context_cost: 3,
    homepage: 'https://exa.ai',
    mcp: {
      url: 'https://mcp.exa.ai/sse',
      env_template: { EXA_API_KEY: '${EXA_API_KEY}' },
    },
    actions: [
      {
        id: 'exa.search',
        name: 'search',
        label: 'Neural Web Search',
        description: 'Perform semantic embeddings search across billions of indexed web pages.',
        params: [
          { name: 'query', type: 'string', required: true, description: 'Natural language query' },
          { name: 'num_results', type: 'number', required: false, description: 'Number of results' },
        ],
        exampleInput: { query: 'latest open source MCP servers released in 2026', num_results: 5 },
        risk: 'low',
      }
    ],
    triggers: []
  },

  // 32. Hugging Face
  {
    name: 'huggingface',
    displayName: 'Hugging Face',
    description: 'Hugging Face Hub AI models, datasets, spaces, papers, and inference APIs.',
    transport: 'http',
    risk: 'medium',
    profiles: ['research', 'cloud', 'ai'],
    category: 'ai',
    authType: 'api_key',
    verified: true,
    enabled: true,
    activeCount: 1,
    env_required: ['HF_TOKEN'],
    env_configured: true,
    context_cost: 5,
    homepage: 'https://huggingface.co',
    mcp: {
      url: 'https://huggingface.co/mcp/sse',
      env_template: { HF_TOKEN: '${HF_TOKEN}' },
    },
    actions: [
      {
        id: 'hf.search_models',
        name: 'search_models',
        label: 'Search Models & Checkpoints',
        description: 'Find weights, model architectures, licenses and download stats on Hugging Face.',
        params: [{ name: 'query', type: 'string', required: true, description: 'Model search keyword' }],
        exampleInput: { query: 'Qwen 2.5 Coder' },
        risk: 'low',
      }
    ],
    triggers: []
  },

  // 33. Memory
  {
    name: 'memory',
    displayName: 'Knowledge Graph Memory',
    description: 'Persistent knowledge graph memory for entities, relations, observations and user preferences.',
    transport: 'stdio',
    risk: 'low',
    profiles: ['reasoning', 'core', 'dev'],
    category: 'ai',
    authType: 'none',
    verified: true,
    enabled: true,
    activeCount: 1,
    env_required: [],
    env_configured: true,
    context_cost: 1,
    homepage: 'https://github.com/modelcontextprotocol/servers',
    mcp: {
      command: 'npx',
      args: ['-y', '@modelcontextprotocol/server-memory@2026.1.26'],
    },
    actions: [
      {
        id: 'memory.create_entities',
        name: 'create_entities',
        label: 'Create Entities',
        description: 'Store new concepts, agents, or user facts in the persistent knowledge graph.',
        params: [{ name: 'entities', type: 'array', required: true, description: 'List of entity nodes' }],
        exampleInput: { entities: [{ name: 'KaterGateway', entityType: 'Service', observations: ['Runs unified on port 3000'] }] },
        risk: 'low',
      }
    ],
    triggers: []
  },

  // 34. Sequential Thinking
  {
    name: 'sequential-thinking',
    displayName: 'Sequential Reasoning',
    description: 'Sequential step-by-step reasoning engine with hypothesis branching and self-correction.',
    transport: 'stdio',
    risk: 'low',
    profiles: ['reasoning', 'research', 'core', 'dev'],
    category: 'ai',
    authType: 'none',
    verified: true,
    enabled: true,
    activeCount: 1,
    env_required: [],
    env_configured: true,
    context_cost: 1,
    homepage: 'https://github.com/modelcontextprotocol/servers',
    mcp: {
      command: 'npx',
      args: ['-y', '@modelcontextprotocol/server-sequential-thinking@2025.12.18'],
    },
    actions: [
      {
        id: 'thinking.step',
        name: 'step',
        label: 'Reasoning Step',
        description: 'Process a structured thought step with hypothesis score, revision, and next step plan.',
        params: [
          { name: 'thought', type: 'string', required: true, description: 'Detailed reasoning analysis' },
          { name: 'thoughtNumber', type: 'number', required: true, description: 'Current step number' },
        ],
        exampleInput: { thought: 'Validating Composio integration parity across all MCP servers in Kater', thoughtNumber: 1 },
        risk: 'low',
      }
    ],
    triggers: []
  },

  // 35. Context7
  {
    name: 'context7',
    displayName: 'Context7 Live Docs',
    description: 'Context7 real-time documentation retrieval for any library, framework, or API specification.',
    transport: 'stdio',
    risk: 'low',
    profiles: ['code', 'research', 'docs', 'dev'],
    category: 'dev',
    authType: 'none',
    verified: true,
    enabled: true,
    activeCount: 1,
    env_required: [],
    env_configured: true,
    context_cost: 2,
    homepage: 'https://context7.com',
    mcp: {
      command: 'npx',
      args: ['-y', '@upstash/context7-mcp@3.2.2'],
    },
    actions: [
      {
        id: 'context7.query_docs',
        name: 'query_docs',
        label: 'Query Library Documentation',
        description: 'Fetch pristine, up-to-date documentation chunks for any package.',
        params: [
          { name: 'package', type: 'string', required: true, description: 'Package name (e.g. zod, express)' },
          { name: 'query', type: 'string', required: true, description: 'Specific method or topic' },
        ],
        exampleInput: { package: 'zod', query: 'environment variable validation with safeParse' },
        risk: 'low',
      }
    ],
    triggers: []
  },

  // 36. Kater Core Gateway
  {
    name: 'kater',
    displayName: 'Kater Core Gateway',
    itemType: 'server',
    description: 'Native Kater core gateway managing profiles, live MCP server proxies, health status, and SQLite state.',
    transport: 'native',
    risk: 'low',
    profiles: ['core', 'ops', 'dev', 'code', 'research', 'content', 'image', 'browser', 'full'],
    category: 'dev',
    authType: 'none',
    verified: true,
    enabled: true,
    activeCount: 1,
    env_required: [],
    env_configured: true,
    context_cost: 0,
    homepage: 'https://github.com/GroepOnline/kater-dev-tools',
    actions: [
      {
        id: 'kater.list_profiles',
        name: 'list_profiles',
        label: 'List Profiles',
        description: 'List available and active execution profiles (e.g. dev, ops, research, browser).',
        params: [],
        exampleInput: {},
        risk: 'low',
      }
    ],
    triggers: []
  },

  // 37. Kater Doctor Diagnostic Plugin
  {
    name: 'kater-doctor',
    displayName: 'Kater Doctor Diagnostic',
    itemType: 'plugin',
    description: 'Automated health audit, port conflict resolution, environment variable linting, and fix-plan synthesis.',
    transport: 'plugin',
    risk: 'low',
    profiles: ['core', 'dev', 'ops', 'full'],
    category: 'plugins',
    authType: 'none',
    verified: true,
    enabled: true,
    activeCount: 1,
    env_required: [],
    env_configured: true,
    context_cost: 1,
    homepage: 'https://github.com/GroepOnline/kater-dev-tools',
    actions: [
      {
        id: 'doctor.run_diagnostics',
        name: 'run_diagnostics',
        label: 'Run System Diagnostics',
        description: 'Inspect gateway port bindings, SQLite integrity, MCP subprocess health, and environment secrets.',
        params: [],
        exampleInput: {},
        risk: 'low',
      }
    ],
    triggers: []
  },

  // 38. Kater E2E MCP Verification Plugin
  {
    name: 'kater-e2e',
    displayName: 'Kater E2E Test Suite',
    itemType: 'plugin',
    description: 'End-to-end integration test runner validating SSE streaming, tool schema negotiation, and WebSocket feeds.',
    transport: 'plugin',
    risk: 'low',
    profiles: ['ops', 'dev', 'full'],
    category: 'plugins',
    authType: 'none',
    verified: true,
    enabled: true,
    activeCount: 1,
    env_required: [],
    env_configured: true,
    context_cost: 1,
    homepage: 'https://github.com/GroepOnline/kater-dev-tools',
    actions: [
      {
        id: 'e2e.verify_mcp_handshake',
        name: 'verify_mcp_handshake',
        label: 'Verify MCP Protocol Handshake',
        description: 'Send test JSON-RPC initialize ping and assert tool listing completeness across active profiles.',
        params: [
          { name: 'profile', type: 'string', required: false, description: 'Profile name to test' }
        ],
        exampleInput: { profile: 'dev' },
        risk: 'low',
      }
    ],
    triggers: []
  },

  // 39. Poteto Mode Playbook Plugin
  {
    name: 'kater-poteto-mode',
    displayName: 'Poteto Mode Satellite',
    itemType: 'plugin',
    description: 'High-speed autonomous playbook agent for rapid bug fixes, refactoring pipelines, and interactive CLI loops.',
    transport: 'plugin',
    risk: 'medium',
    profiles: ['dev', 'code', 'full'],
    category: 'plugins',
    authType: 'none',
    verified: true,
    enabled: true,
    activeCount: 1,
    env_required: [],
    env_configured: true,
    context_cost: 2,
    homepage: 'https://github.com/GroepOnline/kater-dev-tools',
    actions: [
      {
        id: 'poteto.dispatch_playbook',
        name: 'dispatch_playbook',
        label: 'Dispatch Autonomous Playbook',
        description: 'Run automated dev playbook across repository files with continuous test checkpointing.',
        params: [
          { name: 'playbook', type: 'string', required: true, description: 'Playbook identifier or objective' }
        ],
        exampleInput: { playbook: 'audit-mcp-transports' },
        risk: 'medium',
      }
    ],
    triggers: []
  },

  // 40. PR Gate & Merge Verifier Plugin
  {
    name: 'pr-gate',
    displayName: 'PR Gate CI Verifier',
    itemType: 'plugin',
    description: 'Strict merge-ready pull request gate enforcing plain-text workflow invariants, index freshness, and clean test runs.',
    transport: 'plugin',
    risk: 'medium',
    profiles: ['ops', 'dev', 'full'],
    category: 'plugins',
    authType: 'none',
    verified: true,
    enabled: true,
    activeCount: 1,
    env_required: [],
    env_configured: true,
    context_cost: 1,
    homepage: 'https://github.com/GroepOnline/kater-dev-tools',
    actions: [
      {
        id: 'prgate.audit_branch',
        name: 'audit_branch',
        label: 'Audit PR Branch & Artifacts',
        description: 'Verify GitHub Actions YAML integrity, Cursor index artifacts, and pytest pass criteria.',
        params: [
          { name: 'branch', type: 'string', required: false, description: 'Target branch name' }
        ],
        exampleInput: { branch: 'main' },
        risk: 'low',
      }
    ],
    triggers: []
  },

  // 41. CI Fixer Plugin
  {
    name: 'ci-fixer',
    displayName: 'CI & Lint Auto-Fixer',
    itemType: 'plugin',
    description: 'Autonomous test suite healer: analyzes pytest/ruff/mypy failures and applies targeted source code fixes.',
    transport: 'plugin',
    risk: 'high',
    profiles: ['dev', 'ops', 'full'],
    category: 'plugins',
    authType: 'none',
    verified: true,
    enabled: true,
    activeCount: 1,
    env_required: [],
    env_configured: true,
    context_cost: 3,
    homepage: 'https://github.com/GroepOnline/kater-dev-tools',
    actions: [
      {
        id: 'cifixer.heal_failure',
        name: 'heal_failure',
        label: 'Diagnose and Heal CI Failure',
        description: 'Parse test failure trace and generate minimal root-cause patch.',
        params: [
          { name: 'test_output', type: 'string', required: true, description: 'Failing pytest / lint trace' }
        ],
        exampleInput: { test_output: 'AssertionError: assert 200 == 500 in test_gateway.py:42' },
        risk: 'medium',
      }
    ],
    triggers: []
  },

  // 42. ChefGroep Skills Plugin
  {
    name: 'chefgroep-skills',
    displayName: 'ChefGroep Skills Mesh',
    itemType: 'plugin',
    description: 'Cross-repo skill catalog synchronization for reusable agents, command wrappers, and automated prompt hooks.',
    transport: 'plugin',
    risk: 'low',
    profiles: ['core', 'dev', 'full'],
    category: 'plugins',
    authType: 'none',
    verified: true,
    enabled: true,
    activeCount: 1,
    env_required: [],
    env_configured: true,
    context_cost: 1,
    homepage: 'https://github.com/GroepOnline/kater-dev-tools',
    actions: [
      {
        id: 'chefgroep.sync_catalog',
        name: 'sync_catalog',
        label: 'Sync Skills Catalog',
        description: 'Pull latest skill definitions and agent templates into workspace plugins.',
        params: [],
        exampleInput: {},
        risk: 'low',
      }
    ],
    triggers: []
  },

  // 43. Compound Engineering Plugin
  {
    name: 'compound-engineering',
    displayName: 'Compound Engineering Overlay',
    itemType: 'plugin',
    description: 'Tracks persistent architecture logs, design decision artifacts, session summaries, and PR review notes.',
    transport: 'plugin',
    risk: 'low',
    profiles: ['dev', 'ops', 'research', 'full'],
    category: 'plugins',
    authType: 'none',
    verified: true,
    enabled: true,
    activeCount: 1,
    env_required: [],
    env_configured: true,
    context_cost: 1,
    homepage: 'https://github.com/GroepOnline/kater-dev-tools',
    actions: [
      {
        id: 'compound.write_review_log',
        name: 'write_review_log',
        label: 'Write Review Log Entry',
        description: 'Append structured decision record or PR audit note to .reviews/ journal.',
        params: [
          { name: 'title', type: 'string', required: true, description: 'Log title' },
          { name: 'content', type: 'string', required: true, description: 'Markdown note' }
        ],
        exampleInput: { title: 'PR #160 Integrations Architecture', content: 'Added dedicated Integrations tab component with full SVG vector icons and zero emojis.' },
        risk: 'low',
      }
    ],
    triggers: []
  },

  // 44. Docker
  {
    name: 'docker',
    displayName: 'Docker Containers',
    itemType: 'server',
    description: 'Inspect local and remote container registries, tail image logs, inspect port bindings, and run sandboxes.',
    transport: 'stdio',
    risk: 'high',
    profiles: ['ops', 'dev', 'full'],
    category: 'dev',
    authType: 'none',
    verified: true,
    enabled: false,
    env_required: [],
    env_configured: true,
    context_cost: 3,
    homepage: 'https://docker.com',
    actions: [
      {
        id: 'docker.list_containers',
        name: 'list_containers',
        label: 'List Running Containers',
        description: 'Retrieve container IDs, exposed ports, image tags, and uptime status.',
        params: [],
        exampleInput: {},
        risk: 'low',
      }
    ],
    triggers: []
  },

  // 45. Kubernetes
  {
    name: 'kubernetes',
    displayName: 'Kubernetes Cluster',
    itemType: 'server',
    description: 'Inspect cluster pods, query deployment statuses, view container logs, and inspect namespace events.',
    transport: 'stdio',
    risk: 'high',
    profiles: ['ops', 'full'],
    category: 'data',
    authType: 'api_key',
    verified: true,
    enabled: false,
    env_required: ['KUBECONFIG'],
    env_configured: false,
    context_cost: 4,
    homepage: 'https://kubernetes.io',
    actions: [
      {
        id: 'k8s.get_pods',
        name: 'get_pods',
        label: 'Get Namespace Pods',
        description: 'List active pods and readiness probes in a given cluster namespace.',
        params: [
          { name: 'namespace', type: 'string', required: false, description: 'K8s namespace' }
        ],
        exampleInput: { namespace: 'default' },
        risk: 'low',
      }
    ],
    triggers: []
  },

  // 46. Terraform
  {
    name: 'terraform',
    displayName: 'Terraform IaC',
    itemType: 'server',
    description: 'Validate Infrastructure-as-Code state files, inspect resource plans, and check drift status.',
    transport: 'stdio',
    risk: 'high',
    profiles: ['ops', 'dev', 'full'],
    category: 'dev',
    authType: 'none',
    verified: true,
    enabled: false,
    env_required: [],
    env_configured: true,
    context_cost: 3,
    homepage: 'https://terraform.io',
    actions: [
      {
        id: 'terraform.plan_summary',
        name: 'plan_summary',
        label: 'Get Plan Summary',
        description: 'Analyze proposed cloud infrastructure resource changes.',
        params: [],
        exampleInput: {},
        risk: 'low',
      }
    ],
    triggers: []
  },

  // 47. Discord
  {
    name: 'discord',
    displayName: 'Discord Bot & Webhooks',
    itemType: 'server',
    description: 'Post build alerts, dispatch agent messages, and listen to developer community channels.',
    transport: 'http',
    risk: 'medium',
    profiles: ['comm', 'ops', 'dev', 'full'],
    category: 'comm',
    authType: 'api_key',
    verified: true,
    enabled: false,
    env_required: ['DISCORD_BOT_TOKEN'],
    env_configured: false,
    context_cost: 2,
    homepage: 'https://discord.com',
    actions: [
      {
        id: 'discord.send_channel_message',
        name: 'send_channel_message',
        label: 'Send Channel Message',
        description: 'Post a rich embedded alert or message to a Discord server channel.',
        params: [
          { name: 'channel_id', type: 'string', required: true, description: 'Target Discord channel ID' },
          { name: 'content', type: 'string', required: true, description: 'Message markdown content' }
        ],
        exampleInput: { channel_id: '1092837465', content: 'Kater Gateway CI run succeeded.' },
        risk: 'low',
      }
    ],
    triggers: []
  },

  // 48. Telegram
  {
    name: 'telegram',
    displayName: 'Telegram Bot API',
    itemType: 'server',
    description: 'Send instant push alerts, deployment notifications, and prompt responses directly to chat groups.',
    transport: 'http',
    risk: 'medium',
    profiles: ['comm', 'ops', 'dev', 'full'],
    category: 'comm',
    authType: 'api_key',
    verified: true,
    enabled: false,
    env_required: ['TELEGRAM_BOT_TOKEN'],
    env_configured: false,
    context_cost: 2,
    homepage: 'https://telegram.org',
    actions: [
      {
        id: 'telegram.send_message',
        name: 'send_message',
        label: 'Send Telegram Message',
        description: 'Dispatch an alert message to a chat ID.',
        params: [
          { name: 'chat_id', type: 'string', required: true, description: 'Telegram chat or group ID' },
          { name: 'text', type: 'string', required: true, description: 'Text message' }
        ],
        exampleInput: { chat_id: '@kater_alerts', text: 'Gateway deployment live on port 3000' },
        risk: 'low',
      }
    ],
    triggers: []
  }
];
