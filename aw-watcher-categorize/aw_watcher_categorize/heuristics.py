"""
Detailed hierarchical heuristics and knowledge base for ActivityWatch.
Organized into rich, related groups with 3-4 levels of granularity.
"""

from typing import List, Tuple, Dict, Any

BUILTIN_HEURISTICS: List[Tuple[List[str], str]] = [
    # -------------------------------------------------------------
    # 1. Work > Software Engineering
    # -------------------------------------------------------------
    (
        ["Work", "Software Engineering", "IDEs & Editors", "Antigravity IDE"],
        r"(?i)\b(Antigravity IDE)\b",
    ),
    (
        ["Work", "Software Engineering", "IDEs & Editors", "VS Code"],
        r"(?i)\b(Visual Studio Code|VSCode|Code\.exe)\b",
    ),
    (
        ["Work", "Software Engineering", "IDEs & Editors", "JetBrains"],
        r"(?i)\b(PyCharm|IntelliJ|WebStorm|CLion|Rider|DataGrip|GoLand|PhpStorm|RubyMine)\b",
    ),
    (
        ["Work", "Software Engineering", "IDEs & Editors", "AI Code Editors"],
        r"(?i)\b(Cursor|Zed|Windsurf|Aider)\b",
    ),
    (
        ["Work", "Software Engineering", "IDEs & Editors", "Terminal Editors"],
        r"(?i)\b(Neovim|nvim|vim|Emacs|Nano|Helix|Kakoune|Micro)\b",
    ),
    (
        ["Work", "Software Engineering", "AI & Machine Learning", "ActivityWatch AI"],
        r"(?i)\b(ActivityWatch|aw-watcher|aw-server|aw-client|aw-core|aw-qt)\b",
    ),
    (
        ["Work", "Software Engineering", "AI & Machine Learning", "LLMs & Agents"],
        r"(?i)\b(ChatGPT|OpenAI|Claude|Anthropic|Gemini|Google AI Studio|Ollama|HuggingFace|LangChain|LlamaIndex|DeepSeek|Perplexity|Midjourney)\b",
    ),
    (
        ["Work", "Software Engineering", "Version Control", "Git & GitHub"],
        r"(?i)\b(GitHub|GitLab|Bitbucket|GitKraken|SourceTree|Tower|Fork|Gitea|git\.exe|Git-)\b",
    ),
    (
        ["Work", "Software Engineering", "DevOps & Cloud", "Containers & Orchestration"],
        r"(?i)\b(Docker|Docker Desktop|Kubernetes|kubectl|k8s|Podman|Helm|Minikube)\b",
    ),
    (
        ["Work", "Software Engineering", "DevOps & Cloud", "Cloud Platforms"],
        r"(?i)\b(AWS Console|Google Cloud Console|Azure Portal|Cloudflare|Vercel|Netlify|Heroku|DigitalOcean|Supabase|Firebase)\b",
    ),
    (
        ["Work", "Software Engineering", "DevOps & Cloud", "Infrastructure & IaC"],
        r"(?i)\b(Terraform|Ansible|Pulumi|Vagrant|Puppet|Chef)\b",
    ),
    (
        ["Work", "Software Engineering", "Databases & Tools", "Clients & GUIs"],
        r"(?i)\b(DBeaver|TablePlus|DataGrip|pgAdmin|MySQL Workbench|MongoDB Compass|RedisInsight|Postico)\b",
    ),
    (
        ["Work", "Software Engineering", "API & Network Tools", "Testing & Debugging"],
        r"(?i)\b(Postman|Insomnia|Hoppscotch|Bruno|Wireshark|Charles Proxy|Fiddler)\b",
    ),
    (
        ["Work", "Software Engineering", "Terminal & Shell", "Consoles"],
        r"(?i)\b(Windows Terminal|powershell\.exe|pwsh|cmd\.exe|iTerm|Alacritty|Kitty|WezTerm|Hyper|bash|zsh|fish)\b",
    ),

    # -------------------------------------------------------------
    # 2. Work > Design & Creative
    # -------------------------------------------------------------
    (
        ["Work", "Design & Creative", "UI & UX Design", "Figma"],
        r"(?i)\b(Figma|Sketch|Adobe XD|InVision|Framer)\b",
    ),
    (
        ["Work", "Design & Creative", "Graphic Design & Illustration", "Adobe Suite"],
        r"(?i)\b(Photoshop|Illustrator|InDesign|Lightroom|Affinity Designer|Affinity Photo|CorelDRAW)\b",
    ),
    (
        ["Work", "Design & Creative", "Graphic Design & Illustration", "Open Source"],
        r"(?i)\b(GIMP|Inkscape|Krita|Canva)\b",
    ),
    (
        ["Work", "Design & Creative", "3D Modeling & CAD", "3D Suites"],
        r"(?i)\b(Blender|Autodesk Maya|3ds Max|Cinema 4D|ZBrush|Houdini)\b",
    ),
    (
        ["Work", "Design & Creative", "3D Modeling & CAD", "CAD & Engineering"],
        r"(?i)\b(AutoCAD|Fusion 360|SolidWorks|FreeCAD|Rhino|Onshape|Inventor)\b",
    ),
    (
        ["Work", "Design & Creative", "Video & Motion", "Video Editing"],
        r"(?i)\b(Premiere Pro|DaVinci Resolve|Final Cut Pro|After Effects|Kdenlive|Shotcut|CapCut)\b",
    ),
    (
        ["Work", "Design & Creative", "Audio & Music Production", "DAWs & Recording"],
        r"(?i)\b(Audacity|Ableton Live|FL Studio|Logic Pro|Pro Tools|Reaper|Cubase|Bitwig|Studio One)\b",
    ),

    # -------------------------------------------------------------
    # 3. Communication & Collaboration
    # -------------------------------------------------------------
    (
        ["Communication & Collaboration", "Team Chat", "Workspaces"],
        r"(?i)\b(Slack|Microsoft Teams|Mattermost|Zulip|Element|Matrix|Riot|Rambox)\b",
    ),
    (
        ["Communication & Collaboration", "Instant Messaging", "Personal & Social"],
        r"(?i)\b(Discord|Telegram|WhatsApp|Signal|Messenger|WeChat|Viber|Line)\b",
    ),
    (
        ["Communication & Collaboration", "Email & Inbox", "Clients & Webmail"],
        r"(?i)\b(Gmail|Thunderbird|Outlook|Mailspring|ProtonMail|Fastmail|Hey\.com|Apple Mail|mutt|alpine)\b",
    ),
    (
        ["Communication & Collaboration", "Video Calls & Meetings", "Conferencing"],
        r"(?i)\b(Zoom|Google Meet|Teams Meeting|Webex|Skype|Jitsi Meet|GoToMeeting)\b",
    ),

    # -------------------------------------------------------------
    # 4. Research & Learning
    # -------------------------------------------------------------
    (
        ["Research & Learning", "Developer Documentation", "Q&A & Reference"],
        r"(?i)\b(Stack Overflow|StackExchange|MDN Web Docs|DevDocs|Rust Docs|Python Docs|pkg\.go\.dev|crates\.io|npmjs\.com|pypi\.org|docs\.rs)\b",
    ),
    (
        ["Research & Learning", "Academic & Scientific", "Papers & Encyclopedias"],
        r"(?i)\b(Wikipedia|ArXiv|Google Scholar|ResearchGate|Semantic Scholar|JSTOR|PubMed|ScienceDirect|IEEE Xplore|Zotero|Mendeley)\b",
    ),
    (
        ["Research & Learning", "Courses & Learning", "Educational Platforms"],
        r"(?i)\b(Coursera|edX|Udemy|Khan Academy|Pluralsight|Frontend Masters|Codecademy|LeetCode|HackerRank|Exercism|MIT OpenCourseWare)\b",
    ),

    # -------------------------------------------------------------
    # 5. Productivity & Organization
    # -------------------------------------------------------------
    (
        ["Productivity & Organization", "Note Taking & Knowledge Base", "Connected Notes"],
        r"(?i)\b(Notion|Obsidian|Logseq|Roam Research|Anytype|Bear|Craft|RemNote)\b",
    ),
    (
        ["Productivity & Organization", "Note Taking & Knowledge Base", "General Notes"],
        r"(?i)\b(Evernote|OneNote|Joplin|Google Keep|Apple Notes|Simplenote)\b",
    ),
    (
        ["Productivity & Organization", "Office & Documents", "Word Processing"],
        r"(?i)\b(Google Docs|Microsoft Word|LibreOffice Writer|Pages|WordPad|ReText)\b",
    ),
    (
        ["Productivity & Organization", "Office & Documents", "Spreadsheets"],
        r"(?i)\b(Google Sheets|Microsoft Excel|LibreOffice Calc|Numbers|Smartsheet)\b",
    ),
    (
        ["Productivity & Organization", "Office & Documents", "Presentations"],
        r"(?i)\b(Google Slides|Microsoft PowerPoint|LibreOffice Impress|Keynote|Pitch|Prezi)\b",
    ),
    (
        ["Productivity & Organization", "Task & Project Management", "Trackers"],
        r"(?i)\b(Jira|Linear|Trello|Asana|Monday\.com|ClickUp|Basecamp|Todoist|Things 3|TickTick)\b",
    ),

    # -------------------------------------------------------------
    # 6. Media & Entertainment
    # -------------------------------------------------------------
    (
        ["Media & Entertainment", "Video & Streaming", "YouTube"],
        r"(?i)\b(YouTube|YouTube Music)\b",
    ),
    (
        ["Media & Entertainment", "Video & Streaming", "Movies & TV"],
        r"(?i)\b(Netflix|Twitch|Disney\+|Hulu|HBO Max|Prime Video|Plex|Crunchyroll|Stremio)\b",
    ),
    (
        ["Media & Entertainment", "Video & Streaming", "Media Players"],
        r"(?i)\b(VLC|IINA|mpv|PotPlayer|KMPlayer|Windows Media Player)\b",
    ),
    (
        ["Media & Entertainment", "Music & Audio", "Streaming & Podcasts"],
        r"(?i)\b(Spotify|Apple Music|Tidal|Deezer|SoundCloud|Bandcamp|Pocket Casts|Overcast|Foobar2000|AIMP)\b",
    ),
    (
        ["Media & Entertainment", "Social Media", "Feeds & Discussion"],
        r"(?i)\b(Reddit|Twitter|X\.com|TweetDeck|Facebook|Instagram|Threads|TikTok|Mastodon|Bluesky|LinkedIn|Pinterest|devRant)\b",
    ),
    (
        ["Media & Entertainment", "Gaming", "Stores & Launchers"],
        r"(?i)\b(Steam|Epic Games|Battle\.net|GOG Galaxy|EA App|Ubisoft Connect|Xbox App)\b",
    ),
    (
        ["Media & Entertainment", "Gaming", "Games & Engines"],
        r"(?i)\b(Minecraft|RimWorld|League of Legends|Valorant|CS:GO|Counter-Strike|Dota 2|Overwatch|Fortnite|Roblox|Unity|Unreal Editor|Godot)\b",
    ),

    # -------------------------------------------------------------
    # 7. System & Utilities
    # -------------------------------------------------------------
    (
        ["System & Utilities", "File Management", "Explorers"],
        r"(?i)\b(explorer\.exe|File Explorer|Total Commander|Directory Opus|Double Commander|7-Zip|WinRAR)\b",
    ),
    (
        ["System & Utilities", "OS & Shell", "System Tools"],
        r"(?i)\b(ShellExperienceHost|Taskmgr|Task Manager|Control Panel|Windows Settings|System Settings|Resource Monitor)\b",
    ),
    (
        ["System & Utilities", "Web Browsing", "Browsers"],
        r"(?i)\b(msedge\.exe|Microsoft Edge|chrome\.exe|Google Chrome|firefox\.exe|Mozilla Firefox|brave\.exe|Brave Browser|Opera|Vivaldi|Safari|Arc)\b",
    ),
]


def get_builtin_classes() -> List[Tuple[List[str], Dict[str, Any]]]:
    """Returns the builtin heuristics in the standard ActivityWatch classes format."""
    return [
        (category, {"type": "regex", "regex": regex, "ignore_case": True})
        for category, regex in BUILTIN_HEURISTICS
    ]
