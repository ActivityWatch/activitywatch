# aw-watcher-categorize live daemon for ActivityWatch with Gemini AI Integration & Deep Hierarchy
$ErrorActionPreference = "Continue"

$hostName = "TDS_46"
$bucketId = "aw-watcher-categorize_$hostName"
$serverUrl = "http://localhost:5600"
$configPath = [System.IO.Path]::Combine([System.Environment]::GetFolderPath('LocalApplicationData'), "activitywatch\activitywatch\aw-watcher-categorize\aw-watcher-categorize.toml")
$apiKey = $env:GEMINI_API_KEY
$model = if ($env:GEMINI_MODEL) { $env:GEMINI_MODEL } else { "gemini-2.5-flash" }

if (Test-Path $configPath) {
    $content = Get-Content $configPath -Raw
    if ($content -match 'ai_api_key\s*=\s*"([^"]+)"' -and -not $apiKey) {
        $apiKey = $matches[1]
    }
    if ($content -match 'ai_model\s*=\s*"([^"]+)"') {
        $model = $matches[1]
    }
}
$cache = @{}

Write-Output "Starting aw-watcher-categorize live watcher daemon with Gemini AI (Deep Granular Hierarchy) for host $hostName..."

# Ensure bucket exists
$bucketData = @{
    client = "aw-watcher-categorize"
    hostname = $hostName
    type = "categorization"
} | ConvertTo-Json

try {
    Invoke-RestMethod -Uri "$serverUrl/api/0/buckets/$bucketId" -Method Post -Body $bucketData -ContentType "application/json" -ErrorAction SilentlyContinue
} catch {}

function Query-Gemini-Category ($app, $title) {
    if (-not $apiKey) {
        return @{ category = @("Uncategorized"); confidence = 0.0; regex = "" }
    }
    $cacheKey = "$app|||$title"
    if ($cache.ContainsKey($cacheKey)) {
        return $cache[$cacheKey]
    }

    try {
        $endpoint = "https://generativelanguage.googleapis.com/v1beta/models/$($model):generateContent?key=$apiKey"
        $prompt = @"
You are an expert activity categorization assistant for ActivityWatch.
Classify this computer window/app activity into a granular, deep 3-to-4 level hierarchy organized into one of the following related groups:

- Work > Software Engineering > [IDEs & Editors | AI & Machine Learning | Version Control | DevOps & Cloud | Terminal & Shell | Databases]
- Work > Design & Creative > [UI & UX Design | Graphic Design | 3D & Video | Audio & Music]
- Communication & Collaboration > [Team Chat | Instant Messaging | Email & Inbox | Video Calls & Meetings]
- Research & Learning > [Developer Documentation | Academic & Scientific | Courses & Learning]
- Productivity & Organization > [Note Taking & Knowledge Base | Office & Documents | Task & Project Management]
- Media & Entertainment > [Video & Streaming | Music & Audio | Social Media | Gaming]
- System & Utilities > [File Management | OS & Shell | Web Browsing]

Activity to classify:
App: $app
Title: $title

Return ONLY valid JSON matching this structure without markdown:
{"category": ["RootGroup", "SubGroup", "SpecificDomain", "Topic"], "regex": "pattern", "confidence": 0.95}
"@

        $body = @{
            contents = @(
                @{
                    parts = @(
                        @{ text = $prompt }
                    )
                }
            )
            generationConfig = @{
                temperature = 0.1
                responseMimeType = "application/json"
            }
        } | ConvertTo-Json -Depth 5

        $res = Invoke-RestMethod -Uri $endpoint -Method Post -Body $body -ContentType "application/json" -TimeoutSec 10
        $text = $res.candidates[0].content.parts[0].text.Trim()
        $json = $text | ConvertFrom-Json
        
        $catArray = @()
        foreach ($c in $json.category) { $catArray += [string]$c }
        if ($catArray.Count -eq 0) { $catArray = @("Uncategorized") }
        
        $result = @{
            category = $catArray
            confidence = [double]$json.confidence
            regex = [string]$json.regex
        }
        $cache[$cacheKey] = $result
        return $result
    } catch {
        return @{ category = @("Uncategorized"); confidence = 0.0; regex = "" }
    }
}

function Classify-Activity ($app, $title) {
    $text = "$app $title"
    
    # 1. Work > Software Engineering
    if ($text -match "(?i)Antigravity IDE") {
        return @{ category = @("Work", "Software Engineering", "IDEs & Editors", "Antigravity IDE"); confidence = 1.0; source = "heuristics" }
    }
    if ($text -match "(?i)VSCode|Visual Studio Code|Code\.exe") {
        return @{ category = @("Work", "Software Engineering", "IDEs & Editors", "VS Code"); confidence = 1.0; source = "heuristics" }
    }
    if ($text -match "(?i)PyCharm|IntelliJ|WebStorm|CLion|Rider|DataGrip") {
        return @{ category = @("Work", "Software Engineering", "IDEs & Editors", "JetBrains"); confidence = 1.0; source = "heuristics" }
    }
    if ($text -match "(?i)ActivityWatch|aw-watcher|aw-server|aw-client|aw-core|aw-qt") {
        return @{ category = @("Work", "Software Engineering", "AI & Machine Learning", "ActivityWatch AI"); confidence = 1.0; source = "heuristics" }
    }
    if ($text -match "(?i)ChatGPT|OpenAI|Claude|Anthropic|Gemini|Google AI Studio|Ollama|HuggingFace|DeepSeek|Perplexity") {
        return @{ category = @("Work", "Software Engineering", "AI & Machine Learning", "LLMs & AI Assistants"); confidence = 1.0; source = "heuristics" }
    }
    if ($text -match "(?i)Git-|git\.exe|GitHub|GitLab|Bitbucket|GitKraken|SourceTree") {
        return @{ category = @("Work", "Software Engineering", "Version Control", "Git & GitHub"); confidence = 1.0; source = "heuristics" }
    }
    if ($text -match "(?i)Windows Terminal|powershell\.exe|pwsh|cmd\.exe|bash|zsh|fish|iTerm") {
        return @{ category = @("Work", "Software Engineering", "Terminal & Shell"); confidence = 1.0; source = "heuristics" }
    }
    
    # 2. Design & Creative
    if ($text -match "(?i)Figma|Sketch|Adobe XD|Framer") {
        return @{ category = @("Work", "Design & Creative", "UI & UX Design"); confidence = 1.0; source = "heuristics" }
    }
    if ($text -match "(?i)Photoshop|Illustrator|InDesign|GIMP|Inkscape|Canva") {
        return @{ category = @("Work", "Design & Creative", "Graphic Design"); confidence = 1.0; source = "heuristics" }
    }
    if ($text -match "(?i)Blender|Maya|Premiere Pro|DaVinci Resolve|After Effects|Kdenlive|Audacity") {
        return @{ category = @("Work", "Design & Creative", "3D & Video"); confidence = 1.0; source = "heuristics" }
    }

    # 3. Communication & Collaboration
    if ($text -match "(?i)Slack|Microsoft Teams|Mattermost|Zulip|Element") {
        return @{ category = @("Communication & Collaboration", "Team Chat"); confidence = 1.0; source = "heuristics" }
    }
    if ($text -match "(?i)Discord|Telegram|WhatsApp|Signal|Messenger") {
        return @{ category = @("Communication & Collaboration", "Instant Messaging"); confidence = 1.0; source = "heuristics" }
    }
    if ($text -match "(?i)Gmail|Thunderbird|Outlook|Mailspring|ProtonMail") {
        return @{ category = @("Communication & Collaboration", "Email & Inbox"); confidence = 1.0; source = "heuristics" }
    }
    if ($text -match "(?i)Zoom|Google Meet|Teams Meeting|Webex") {
        return @{ category = @("Communication & Collaboration", "Video Calls & Meetings"); confidence = 1.0; source = "heuristics" }
    }

    # 4. Research & Learning
    if ($text -match "(?i)Stack Overflow|StackExchange|MDN Web Docs|DevDocs|Rust Docs|Python Docs|pkg\.go\.dev|crates\.io|npmjs\.com|pypi\.org") {
        return @{ category = @("Research & Learning", "Developer Documentation"); confidence = 1.0; source = "heuristics" }
    }
    if ($text -match "(?i)Wikipedia|ArXiv|Google Scholar|ResearchGate|Semantic Scholar|JSTOR") {
        return @{ category = @("Research & Learning", "Academic & Scientific"); confidence = 1.0; source = "heuristics" }
    }

    # 5. Productivity & Organization
    if ($text -match "(?i)Notion|Obsidian|Logseq|Roam Research|Evernote|OneNote|Joplin|Google Keep") {
        return @{ category = @("Productivity & Organization", "Note Taking & Knowledge Base"); confidence = 1.0; source = "heuristics" }
    }
    if ($text -match "(?i)Google Docs|Google Sheets|Google Slides|Microsoft Word|Microsoft Excel|Microsoft PowerPoint|LibreOffice") {
        return @{ category = @("Productivity & Organization", "Office & Documents"); confidence = 1.0; source = "heuristics" }
    }

    # 6. Media & Entertainment
    if ($text -match "(?i)YouTube|Netflix|Twitch|Disney\+|Prime Video|Plex|VLC") {
        return @{ category = @("Media & Entertainment", "Video & Streaming"); confidence = 1.0; source = "heuristics" }
    }
    if ($text -match "(?i)Spotify|Apple Music|Tidal|Deezer|SoundCloud|Bandcamp") {
        return @{ category = @("Media & Entertainment", "Music & Audio"); confidence = 1.0; source = "heuristics" }
    }
    if ($text -match "(?i)Reddit|Twitter|X\.com|TweetDeck|Facebook|Instagram|Threads|TikTok|Mastodon|Bluesky|LinkedIn") {
        return @{ category = @("Media & Entertainment", "Social Media"); confidence = 1.0; source = "heuristics" }
    }

    # 7. System & Utilities
    if ($text -match "(?i)explorer\.exe|File Explorer|Total Commander|7-Zip|WinRAR") {
        return @{ category = @("System & Utilities", "File Management"); confidence = 1.0; source = "heuristics" }
    }
    if ($text -match "(?i)ShellExperienceHost|Taskmgr|Task Manager|Control Panel|Windows Settings") {
        return @{ category = @("System & Utilities", "OS & Shell"); confidence = 1.0; source = "heuristics" }
    }
    if ($text -match "(?i)msedge\.exe|Microsoft Edge|chrome\.exe|Google Chrome|firefox\.exe|Mozilla Firefox|brave\.exe") {
        return @{ category = @("System & Utilities", "Web Browsing"); confidence = 1.0; source = "heuristics" }
    }
    
    # AI Fallback for unrecognized activities
    $aiRes = Query-Gemini-Category $app $title
    return @{ category = $aiRes.category; confidence = $aiRes.confidence; source = "gemini_ai"; regex = $aiRes.regex }
}

$pollTime = 5
$pulseTime = 10

while ($true) {
    try {
        $events = Invoke-RestMethod -Uri "$serverUrl/api/0/buckets/aw-watcher-window_$hostName/events?limit=1" -Method Get
        if ($events -and $events.Count -gt 0) {
            $latest = $events[0]
            $app = if ($latest.data.app) { $latest.data.app } else { "" }
            $title = if ($latest.data.title) { $latest.data.title } else { "" }

            $classification = Classify-Activity $app $title
            $nowIso = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss.ffffff+00:00")

            $heartbeatEvent = @{
                timestamp = $nowIso
                duration = 0.0
                data = @{
                    app = $app
                    title = $title
                    '$category' = $classification.category
                    confidence = $classification.confidence
                    source = $classification.source
                }
            } | ConvertTo-Json -Depth 5

            $heartbeatUrl = "$serverUrl/api/0/buckets/$bucketId/heartbeat?pulsetime=$pulseTime"
            Invoke-RestMethod -Uri $heartbeatUrl -Method Post -Body $heartbeatEvent -ContentType "application/json" | Out-Null
        }
    } catch {}
    Start-Sleep -Seconds $pollTime
}
