#!/usr/bin/env python3
"""Patch aw-watcher-window/config.py with Matthias's research edition category maps.

Run as part of the CI build for research edition:
    python3 scripts/patch_research_edition_config.py <path/to/config.py>

Two maps are injected:

CATEGORY_MAP — browser URL/title substring matching:
    classify_title() in PR #130 checks each pattern against the URL first (when
    available), then the window title. Ordering is critical: first match wins.
    Sensitive exclusions must come first. More specific domains before general
    (music.youtube.com before youtube.com). Video domains before News title keywords
    (svtplay.se domain before the "svt" title keyword).

APP_CATEGORY_MAP — non-browser app-name → study category mapping:
    classify_app() in PR #136 performs a case-insensitive exact lookup of the
    app name. Non-browser apps are replaced by their study category; unmapped
    apps become 'Excluded'. Ordering within this map is irrelevant (exact lookup).
    Injection fails closed if the [aw-watcher-window.research_app_category_map]
    section is absent, which means the submodule pin predates PR #136.
"""
import pathlib
import re
import sys

CONFIG_FILE = pathlib.Path(
    sys.argv[1] if len(sys.argv) > 1
    else "aw-watcher-window/aw_watcher_window/config.py"
)

# Combined category map derived faithfully from Matthias Lehner's classifier.
# Structure: sensitive domains first, then music/video domains (specificity order),
# then travel/search/other domains, then title keywords in TITLE_RULES priority.
CATEGORY_MAP: list[tuple[str, str]] = [
    # Sensitive / Excluded (MUST be first)
    ("svenskaspel.se", "Sensitive / Excluded"),
    ("unibet.se", "Sensitive / Excluded"),
    ("bet365.com", "Sensitive / Excluded"),
    ("pokerstars.com", "Sensitive / Excluded"),
    ("casino.org", "Sensitive / Excluded"),
    ("tinder.com", "Sensitive / Excluded"),
    ("bumble.com", "Sensitive / Excluded"),
    ("grindr.com", "Sensitive / Excluded"),
    ("match.com", "Sensitive / Excluded"),
    # Music & Audio domains (music.youtube.com before youtube.com; sverigesradio.se before svt.se)
    ("music.youtube.com", "Music & Audio"),
    ("youtube.com/music", "Music & Audio"),
    ("open.spotify.com", "Music & Audio"),
    ("spotify.com", "Music & Audio"),
    ("music.apple.com", "Music & Audio"),
    ("soundcloud.com", "Music & Audio"),
    ("podme.com", "Music & Audio"),
    ("bookbeat.se", "Music & Audio"),
    ("storytel.com", "Music & Audio"),
    ("audible.com", "Music & Audio"),
    ("sverigesradio.se", "Music & Audio"),
    ("sr.se", "Music & Audio"),
    ("radio.se", "Music & Audio"),
    # Video Streaming domains (svtplay.se, svt.se/play before svt.se; tv4.se→Video per Matthias dict)
    ("svt.se/play", "Video Streaming"),
    ("svtplay.se", "Video Streaming"),
    ("tv4play.se", "Video Streaming"),
    ("tv4.se", "Video Streaming"),
    ("youtube.com", "Video Streaming"),
    ("youtu.be", "Video Streaming"),
    ("netflix.com", "Video Streaming"),
    ("viaplay.se", "Video Streaming"),
    ("max.com", "Video Streaming"),
    ("hbomax.com", "Video Streaming"),
    ("primevideo.com", "Video Streaming"),
    ("disneyplus.com", "Video Streaming"),
    ("twitch.tv/directory/game", "Games"),
    ("twitch.tv", "Video Streaming"),
    ("vimeo.com", "Video Streaming"),
    ("dailymotion.com", "Video Streaming"),
    ("kanopy.com", "Video Streaming"),
    ("dr.dk", "Video Streaming"),
    ("nrk.no", "Video Streaming"),
    # Travel & Mobility (maps before google.com)
    ("maps.google.com", "Travel & Mobility"),
    ("google.com/maps", "Travel & Mobility"),
    ("sj.se", "Travel & Mobility"),
    ("sl.se", "Travel & Mobility"),
    ("vasttrafik.se", "Travel & Mobility"),
    ("skanetrafiken.se", "Travel & Mobility"),
    ("resrobot.se", "Travel & Mobility"),
    ("flixbus.se", "Travel & Mobility"),
    ("sas.se", "Travel & Mobility"),
    ("flysas.com", "Travel & Mobility"),
    ("norwegian.com", "Travel & Mobility"),
    ("ryanair.com", "Travel & Mobility"),
    ("airbnb.com", "Travel & Mobility"),
    ("booking.com", "Travel & Mobility"),
    ("hotels.com", "Travel & Mobility"),
    ("tripadvisor.com", "Travel & Mobility"),
    ("uber.com", "Travel & Mobility"),
    ("bolt.eu", "Travel & Mobility"),
    ("parkster.com", "Travel & Mobility"),
    ("easypark.com", "Travel & Mobility"),
    ("circlek.se", "Travel & Mobility"),
    ("okq8.se", "Travel & Mobility"),
    ("preem.se", "Travel & Mobility"),
    # Search & Navigation (google.com after maps.google.com captured above)
    ("google.com", "Search & Navigation"),
    ("google.se", "Search & Navigation"),
    ("bing.com", "Search & Navigation"),
    ("duckduckgo.com", "Search & Navigation"),
    ("yahoo.com", "Search & Navigation"),
    ("startpage.com", "Search & Navigation"),
    ("ecosia.org", "Search & Navigation"),
    ("kagi.com", "Search & Navigation"),
    ("brave.com/search", "Search & Navigation"),
    # News & Current Affairs (svt.se after svt.se/play and svtplay.se)
    ("svt.se", "News & Current Affairs"),
    ("dn.se", "News & Current Affairs"),
    ("dagensnyheter.se", "News & Current Affairs"),
    ("svd.se", "News & Current Affairs"),
    ("aftonbladet.se", "News & Current Affairs"),
    ("expressen.se", "News & Current Affairs"),
    ("gp.se", "News & Current Affairs"),
    ("goteborgsposten.se", "News & Current Affairs"),
    ("sydsvenskan.se", "News & Current Affairs"),
    ("hd.se", "News & Current Affairs"),
    ("unt.se", "News & Current Affairs"),
    ("vk.se", "News & Current Affairs"),
    ("nwt.se", "News & Current Affairs"),
    ("corren.se", "News & Current Affairs"),
    ("omni.se", "News & Current Affairs"),
    ("di.se", "News & Current Affairs"),
    ("dagensindustri.se", "News & Current Affairs"),
    ("breakit.se", "News & Current Affairs"),
    ("nyteknik.se", "News & Current Affairs"),
    ("theguardian.com", "News & Current Affairs"),
    ("bbc.com", "News & Current Affairs"),
    ("bbc.co.uk", "News & Current Affairs"),
    ("cnn.com", "News & Current Affairs"),
    ("edition.cnn.com", "News & Current Affairs"),
    ("aljazeera.com", "News & Current Affairs"),
    ("reuters.com", "News & Current Affairs"),
    ("apnews.com", "News & Current Affairs"),
    ("ft.com", "News & Current Affairs"),
    ("economist.com", "News & Current Affairs"),
    # Social Networking
    ("facebook.com", "Social Networking"),
    ("instagram.com", "Social Networking"),
    ("threads.net", "Social Networking"),
    ("x.com", "Social Networking"),
    ("twitter.com", "Social Networking"),
    ("linkedin.com", "Social Networking"),
    ("mastodon.social", "Social Networking"),
    ("bsky.app", "Social Networking"),
    ("blueskyweb.xyz", "Social Networking"),
    ("bere.al", "Social Networking"),
    ("snapchat.com", "Social Networking"),
    ("pinterest.com", "Social Networking"),
    # Messaging (specific subdomains before parent)
    ("web.whatsapp.com", "Messaging"),
    ("web.telegram.org", "Messaging"),
    ("chat.google.com", "Messaging"),
    ("messages.google.com", "Messaging"),
    ("whatsapp.com", "Messaging"),
    ("messenger.com", "Messaging"),
    ("telegram.org", "Messaging"),
    ("signal.org", "Messaging"),
    ("discord.com", "Messaging"),
    ("discordapp.com", "Messaging"),
    ("slack.com", "Messaging"),
    # Email (specific subdomains before parent)
    ("mail.google.com", "Email"),
    ("icloud.com/mail", "Email"),
    ("zoho.com/mail", "Email"),
    ("outlook.live.com", "Email"),
    ("outlook.office.com", "Email"),
    ("outlook.office365.com", "Email"),
    ("gmail.com", "Email"),
    ("hotmail.com", "Email"),
    ("live.com", "Email"),
    ("mail.yahoo.com", "Email"),
    ("proton.me", "Email"),
    ("protonmail.com", "Email"),
    ("fastmail.com", "Email"),
    # AI Chatbots & Assistants
    ("chat.openai.com", "AI Chatbots & Assistants"),
    ("huggingface.co/chat", "AI Chatbots & Assistants"),
    ("chat.mistral.ai", "AI Chatbots & Assistants"),
    ("gemini.google.com", "AI Chatbots & Assistants"),
    ("notebooklm.google.com", "AI Chatbots & Assistants"),
    ("copilot.microsoft.com", "AI Chatbots & Assistants"),
    ("bard.google.com", "AI Chatbots & Assistants"),
    ("chatgpt.com", "AI Chatbots & Assistants"),
    ("openai.com", "AI Chatbots & Assistants"),
    ("claude.ai", "AI Chatbots & Assistants"),
    ("anthropic.com", "AI Chatbots & Assistants"),
    ("perplexity.ai", "AI Chatbots & Assistants"),
    ("poe.com", "AI Chatbots & Assistants"),
    ("you.com", "AI Chatbots & Assistants"),
    ("mistral.ai", "AI Chatbots & Assistants"),
    ("character.ai", "AI Chatbots & Assistants"),
    ("meta.ai", "AI Chatbots & Assistants"),
    ("grok.com", "AI Chatbots & Assistants"),
    ("x.ai", "AI Chatbots & Assistants"),
    # Work & Productivity
    ("teams.microsoft.com", "Work & Productivity"),
    ("meet.google.com", "Work & Productivity"),
    ("calendar.google.com", "Work & Productivity"),
    ("docs.google.com", "Work & Productivity"),
    ("drive.google.com", "Work & Productivity"),
    ("translate.google.com", "Work & Productivity"),
    ("acrobat.adobe.com", "Work & Productivity"),
    ("onedrive.live.com", "Work & Productivity"),
    ("zoom.us", "Work & Productivity"),
    ("office.com", "Work & Productivity"),
    ("microsoft365.com", "Work & Productivity"),
    ("sharepoint.com", "Work & Productivity"),
    ("dropbox.com", "Work & Productivity"),
    ("notion.so", "Work & Productivity"),
    ("trello.com", "Work & Productivity"),
    ("asana.com", "Work & Productivity"),
    ("monday.com", "Work & Productivity"),
    ("miro.com", "Work & Productivity"),
    ("figma.com", "Work & Productivity"),
    ("canva.com", "Work & Productivity"),
    ("overleaf.com", "Work & Productivity"),
    ("deepl.com", "Work & Productivity"),
    ("adobe.com", "Work & Productivity"),
    ("github.com", "Work & Productivity"),
    ("gitlab.com", "Work & Productivity"),
    ("bitbucket.org", "Work & Productivity"),
    ("atlassian.net", "Work & Productivity"),
    ("jira.com", "Work & Productivity"),
    ("confluence.com", "Work & Productivity"),
    # Education & Learning
    ("stackoverflow.com", "Education & Learning"),
    ("stackexchange.com", "Education & Learning"),
    ("wikipedia.org", "Education & Learning"),
    ("canvaslms.com", "Education & Learning"),
    ("instructure.com", "Education & Learning"),
    ("moodle.org", "Education & Learning"),
    ("blackboard.com", "Education & Learning"),
    ("ladok.se", "Education & Learning"),
    ("antagning.se", "Education & Learning"),
    ("studera.nu", "Education & Learning"),
    ("coursera.org", "Education & Learning"),
    ("edx.org", "Education & Learning"),
    ("khanacademy.org", "Education & Learning"),
    ("duolingo.com", "Education & Learning"),
    ("quizlet.com", "Education & Learning"),
    ("researchgate.net", "Education & Learning"),
    ("academia.edu", "Education & Learning"),
    ("sciencedirect.com", "Education & Learning"),
    ("springer.com", "Education & Learning"),
    ("wiley.com", "Education & Learning"),
    ("tandfonline.com", "Education & Learning"),
    ("jstor.org", "Education & Learning"),
    ("sagepub.com", "Education & Learning"),
    ("mdpi.com", "Education & Learning"),
    ("frontiersin.org", "Education & Learning"),
    # Shopping - Goods
    ("amazon.se", "Shopping - Goods"),
    ("amazon.com", "Shopping - Goods"),
    ("blocket.se", "Shopping - Goods"),
    ("tradera.com", "Shopping - Goods"),
    ("prisjakt.nu", "Shopping - Goods"),
    ("pricerunner.se", "Shopping - Goods"),
    ("elgiganten.se", "Shopping - Goods"),
    ("netonnet.se", "Shopping - Goods"),
    ("mediamarkt.se", "Shopping - Goods"),
    ("inet.se", "Shopping - Goods"),
    ("webhallen.com", "Shopping - Goods"),
    ("komplett.se", "Shopping - Goods"),
    ("zalando.se", "Shopping - Goods"),
    ("hm.com", "Shopping - Goods"),
    ("arket.com", "Shopping - Goods"),
    ("cos.com", "Shopping - Goods"),
    ("ellos.se", "Shopping - Goods"),
    ("boozt.com", "Shopping - Goods"),
    ("ikea.com", "Shopping - Goods"),
    ("clasohlson.com", "Shopping - Goods"),
    ("jula.se", "Shopping - Goods"),
    ("biltema.se", "Shopping - Goods"),
    ("apotea.se", "Shopping - Goods"),
    ("apoteket.se", "Shopping - Goods"),
    ("kronansapotek.se", "Shopping - Goods"),
    ("lyko.com", "Shopping - Goods"),
    ("cdon.se", "Shopping - Goods"),
    ("adlibris.com", "Shopping - Goods"),
    ("bokus.com", "Shopping - Goods"),
    ("wish.com", "Shopping - Goods"),
    ("temu.com", "Shopping - Goods"),
    ("aliexpress.com", "Shopping - Goods"),
    # Shopping - Groceries & Food
    ("ica.se", "Shopping - Groceries & Food"),
    ("coop.se", "Shopping - Groceries & Food"),
    ("willys.se", "Shopping - Groceries & Food"),
    ("hemkop.se", "Shopping - Groceries & Food"),
    ("citygross.se", "Shopping - Groceries & Food"),
    ("mathem.se", "Shopping - Groceries & Food"),
    ("foodora.se", "Shopping - Groceries & Food"),
    ("wolt.com", "Shopping - Groceries & Food"),
    ("ubereats.com", "Shopping - Groceries & Food"),
    ("hellofresh.se", "Shopping - Groceries & Food"),
    ("linasmatkasse.se", "Shopping - Groceries & Food"),
    ("simplefeast.com", "Shopping - Groceries & Food"),
    ("kavall.co", "Shopping - Groceries & Food"),
    # Banking & Finance
    ("swedbank.se", "Banking & Finance"),
    ("seb.se", "Banking & Finance"),
    ("handelsbanken.se", "Banking & Finance"),
    ("nordea.se", "Banking & Finance"),
    ("lansforsakringar.se", "Banking & Finance"),
    ("skandia.se", "Banking & Finance"),
    ("ica-banken.se", "Banking & Finance"),
    ("danskebank.se", "Banking & Finance"),
    ("avanza.se", "Banking & Finance"),
    ("nordnet.se", "Banking & Finance"),
    ("klarna.com", "Banking & Finance"),
    ("paypal.com", "Banking & Finance"),
    ("revolut.com", "Banking & Finance"),
    ("wise.com", "Banking & Finance"),
    ("zettle.com", "Banking & Finance"),
    ("fortnox.se", "Banking & Finance"),
    ("vismaspcs.se", "Banking & Finance"),
    # Public Services
    ("skatteverket.se", "Public Services"),
    ("forsakringskassan.se", "Public Services"),
    ("pensionsmyndigheten.se", "Public Services"),
    ("arbetsformedlingen.se", "Public Services"),
    ("1177.se", "Public Services"),
    ("bankid.com", "Public Services"),
    ("minmyndighetspost.se", "Public Services"),
    ("kivra.se", "Public Services"),
    ("polisen.se", "Public Services"),
    ("migrationsverket.se", "Public Services"),
    ("csn.se", "Public Services"),
    ("trafikverket.se", "Public Services"),
    ("transportstyrelsen.se", "Public Services"),
    ("lantmateriet.se", "Public Services"),
    ("bolagsverket.se", "Public Services"),
    ("verksamt.se", "Public Services"),
    ("stockholm.se", "Public Services"),
    ("goteborg.se", "Public Services"),
    ("malmo.se", "Public Services"),
    ("uppsala.se", "Public Services"),
    ("umea.se", "Public Services"),
    ("lund.se", "Public Services"),
    # Games
    ("steampowered.com", "Games"),
    ("steamcommunity.com", "Games"),
    ("epicgames.com", "Games"),
    ("battle.net", "Games"),
    ("xbox.com", "Games"),
    ("playstation.com", "Games"),
    ("roblox.com", "Games"),
    ("minecraft.net", "Games"),
    ("chess.com", "Games"),
    ("lichess.org", "Games"),
    ("poki.com", "Games"),
    ("miniclip.com", "Games"),
    ("agar.io", "Games"),
    ("forgeofempires.com", "Games"),
    ("catanuniverse.com", "Games"),
    # --- TITLE KEYWORDS (ordered by TITLE_RULES priority) ---
    # Sensitive / Excluded title keywords
    ("svenska spel", "Sensitive / Excluded"),
    ("unibet", "Sensitive / Excluded"),
    ("bet365", "Sensitive / Excluded"),
    ("pokerstars", "Sensitive / Excluded"),
    ("casino", "Sensitive / Excluded"),
    ("tinder", "Sensitive / Excluded"),
    ("bumble", "Sensitive / Excluded"),
    ("grindr", "Sensitive / Excluded"),
    # Travel & Mobility title keywords
    ("google maps", "Travel & Mobility"),
    ("sl reseplanerare", "Travel & Mobility"),
    ("vasttraffik", "Travel & Mobility"),
    ("vasttrafik", "Travel & Mobility"),
    ("skanetrafiken", "Travel & Mobility"),
    ("resrobot", "Travel & Mobility"),
    ("ryanair", "Travel & Mobility"),
    ("booking.com", "Travel & Mobility"),
    ("airbnb", "Travel & Mobility"),
    ("hotels.com", "Travel & Mobility"),
    ("tripadvisor", "Travel & Mobility"),
    ("easypark", "Travel & Mobility"),
    ("parkster", "Travel & Mobility"),
    ("norwegian", "Travel & Mobility"),
    ("flixbus", "Travel & Mobility"),
    ("uber eats", "Shopping - Groceries & Food"),
    ("uber", "Travel & Mobility"),
    ("bolt", "Travel & Mobility"),
    ("maps", "Travel & Mobility"),
    ("sas", "Travel & Mobility"),
    ("sj", "Travel & Mobility"),
    # Shopping - Groceries title keywords
    ("ica", "Shopping - Groceries & Food"),
    ("coop", "Shopping - Groceries & Food"),
    ("willys", "Shopping - Groceries & Food"),
    ("hemköp", "Shopping - Groceries & Food"),
    ("hemkop", "Shopping - Groceries & Food"),
    ("city gross", "Shopping - Groceries & Food"),
    ("mathem", "Shopping - Groceries & Food"),
    ("foodora", "Shopping - Groceries & Food"),
    ("wolt", "Shopping - Groceries & Food"),
    ("hellofresh", "Shopping - Groceries & Food"),
    ("linas matkasse", "Shopping - Groceries & Food"),
    # Shopping - Goods title keywords
    ("amazon", "Shopping - Goods"),
    ("blocket", "Shopping - Goods"),
    ("tradera", "Shopping - Goods"),
    ("prisjakt", "Shopping - Goods"),
    ("pricerunner", "Shopping - Goods"),
    ("elgiganten", "Shopping - Goods"),
    ("netonnet", "Shopping - Goods"),
    ("webhallen", "Shopping - Goods"),
    ("komplett", "Shopping - Goods"),
    ("zalando", "Shopping - Goods"),
    ("h&m", "Shopping - Goods"),
    ("ikea", "Shopping - Goods"),
    ("clas ohlson", "Shopping - Goods"),
    ("jula", "Shopping - Goods"),
    ("biltema", "Shopping - Goods"),
    ("apotea", "Shopping - Goods"),
    ("apoteket", "Shopping - Goods"),
    ("kronans apotek", "Shopping - Goods"),
    ("lyko", "Shopping - Goods"),
    ("cdon", "Shopping - Goods"),
    ("adlibris", "Shopping - Goods"),
    ("bokus", "Shopping - Goods"),
    ("temu", "Shopping - Goods"),
    ("aliexpress", "Shopping - Goods"),
    ("inet", "Shopping - Goods"),
    # Banking & Finance title keywords
    ("swedbank", "Banking & Finance"),
    ("handelsbanken", "Banking & Finance"),
    ("länsförsäkringar", "Banking & Finance"),
    ("lansforsakringar", "Banking & Finance"),
    ("skandia", "Banking & Finance"),
    ("ica banken", "Banking & Finance"),
    ("avanza", "Banking & Finance"),
    ("nordnet", "Banking & Finance"),
    ("klarna", "Banking & Finance"),
    ("paypal", "Banking & Finance"),
    ("revolut", "Banking & Finance"),
    ("wise", "Banking & Finance"),
    ("fortnox", "Banking & Finance"),
    ("visma", "Banking & Finance"),
    ("nordea", "Banking & Finance"),
    ("seb", "Banking & Finance"),
    # Public Services title keywords
    ("skatteverket", "Public Services"),
    ("försäkringskassan", "Public Services"),
    ("forsakringskassan", "Public Services"),
    ("pensionsmyndigheten", "Public Services"),
    ("arbetsförmedlingen", "Public Services"),
    ("arbetsformedlingen", "Public Services"),
    ("1177", "Public Services"),
    ("bankid", "Public Services"),
    ("min myndighetspost", "Public Services"),
    ("kivra", "Public Services"),
    ("polisen", "Public Services"),
    ("migrationsverket", "Public Services"),
    ("csn", "Public Services"),
    ("trafikverket", "Public Services"),
    ("transportstyrelsen", "Public Services"),
    ("lantmäteriet", "Public Services"),
    ("lantmateriet", "Public Services"),
    ("bolagsverket", "Public Services"),
    ("verksamt", "Public Services"),
    # AI Chatbots & Assistants title keywords
    ("chatgpt", "AI Chatbots & Assistants"),
    ("chat.openai", "AI Chatbots & Assistants"),
    ("openai", "AI Chatbots & Assistants"),
    ("claude", "AI Chatbots & Assistants"),
    ("anthropic", "AI Chatbots & Assistants"),
    ("gemini", "AI Chatbots & Assistants"),
    ("google gemini", "AI Chatbots & Assistants"),
    ("bard", "AI Chatbots & Assistants"),
    ("microsoft copilot", "AI Chatbots & Assistants"),
    ("copilot", "AI Chatbots & Assistants"),
    ("perplexity", "AI Chatbots & Assistants"),
    ("poe", "AI Chatbots & Assistants"),
    ("you.com", "AI Chatbots & Assistants"),
    ("mistral", "AI Chatbots & Assistants"),
    ("le chat", "AI Chatbots & Assistants"),
    ("huggingchat", "AI Chatbots & Assistants"),
    ("hugging face chat", "AI Chatbots & Assistants"),
    ("character.ai", "AI Chatbots & Assistants"),
    ("meta ai", "AI Chatbots & Assistants"),
    ("grok", "AI Chatbots & Assistants"),
    ("notebooklm", "AI Chatbots & Assistants"),
    ("notebook lm", "AI Chatbots & Assistants"),
    # Work & Productivity title keywords
    ("microsoft teams", "Work & Productivity"),
    ("teams", "Work & Productivity"),
    ("zoom", "Work & Productivity"),
    ("google meet", "Work & Productivity"),
    ("google calendar", "Work & Productivity"),
    ("google kalender", "Work & Productivity"),
    ("google docs", "Work & Productivity"),
    ("google dokument", "Work & Productivity"),
    ("google sheets", "Work & Productivity"),
    ("google kalkylark", "Work & Productivity"),
    ("google slides", "Work & Productivity"),
    ("google presentationer", "Work & Productivity"),
    ("google drive", "Work & Productivity"),
    ("office", "Work & Productivity"),
    ("microsoft 365", "Work & Productivity"),
    ("onedrive", "Work & Productivity"),
    ("sharepoint", "Work & Productivity"),
    ("dropbox", "Work & Productivity"),
    ("notion", "Work & Productivity"),
    ("trello", "Work & Productivity"),
    ("asana", "Work & Productivity"),
    ("miro", "Work & Productivity"),
    ("figma", "Work & Productivity"),
    ("canva", "Work & Productivity"),
    ("overleaf", "Work & Productivity"),
    ("deepl", "Work & Productivity"),
    ("google translate", "Work & Productivity"),
    ("adobe", "Work & Productivity"),
    ("acrobat", "Work & Productivity"),
    ("github", "Work & Productivity"),
    ("gitlab", "Work & Productivity"),
    ("jira", "Work & Productivity"),
    ("confluence", "Work & Productivity"),
    # Education & Learning title keywords
    ("wikipedia", "Education & Learning"),
    ("canvas", "Education & Learning"),
    ("moodle", "Education & Learning"),
    ("blackboard", "Education & Learning"),
    ("ladok", "Education & Learning"),
    ("antagning", "Education & Learning"),
    ("coursera", "Education & Learning"),
    ("edx", "Education & Learning"),
    ("khan academy", "Education & Learning"),
    ("duolingo", "Education & Learning"),
    ("quizlet", "Education & Learning"),
    ("stack overflow", "Education & Learning"),
    ("stackexchange", "Education & Learning"),
    ("researchgate", "Education & Learning"),
    ("sciencedirect", "Education & Learning"),
    ("springer", "Education & Learning"),
    ("wiley", "Education & Learning"),
    ("jstor", "Education & Learning"),
    ("sage journals", "Education & Learning"),
    ("taylor & francis", "Education & Learning"),
    # Email title keywords
    ("gmail", "Email"),
    ("outlook", "Email"),
    ("hotmail", "Email"),
    ("yahoo mail", "Email"),
    ("proton mail", "Email"),
    ("protonmail", "Email"),
    ("icloud mail", "Email"),
    ("zoho mail", "Email"),
    ("fastmail", "Email"),
    # Messaging title keywords
    ("whatsapp", "Messaging"),
    ("messenger", "Messaging"),
    ("telegram", "Messaging"),
    ("signal", "Messaging"),
    ("discord", "Messaging"),
    ("slack", "Messaging"),
    ("google chat", "Messaging"),
    ("messages", "Messaging"),
    # Social Networking title keywords
    ("facebook", "Social Networking"),
    ("instagram", "Social Networking"),
    ("threads", "Social Networking"),
    ("twitter", "Social Networking"),
    ("x.com", "Social Networking"),
    ("linkedin", "Social Networking"),
    ("mastodon", "Social Networking"),
    ("bluesky", "Social Networking"),
    ("bsky", "Social Networking"),
    ("bereal", "Social Networking"),
    ("snapchat", "Social Networking"),
    ("pinterest", "Social Networking"),
    # Video Streaming title keywords
    ("youtube", "Video Streaming"),
    ("netflix", "Video Streaming"),
    ("svt play", "Video Streaming"),
    ("tv4 play", "Video Streaming"),
    ("viaplay", "Video Streaming"),
    ("hbo max", "Video Streaming"),
    ("hbomax", "Video Streaming"),
    ("prime video", "Video Streaming"),
    ("disney+", "Video Streaming"),
    ("disney plus", "Video Streaming"),
    ("twitch", "Video Streaming"),
    ("vimeo", "Video Streaming"),
    ("dailymotion", "Video Streaming"),
    # Music & Audio title keywords
    ("spotify", "Music & Audio"),
    ("apple music", "Music & Audio"),
    ("youtube music", "Music & Audio"),
    ("soundcloud", "Music & Audio"),
    ("podme", "Music & Audio"),
    ("bookbeat", "Music & Audio"),
    ("storytel", "Music & Audio"),
    ("audible", "Music & Audio"),
    ("sveriges radio", "Music & Audio"),
    ("sr play", "Music & Audio"),
    # Games title keywords
    ("steam", "Games"),
    ("epic games", "Games"),
    ("battle.net", "Games"),
    ("xbox", "Games"),
    ("playstation", "Games"),
    ("roblox", "Games"),
    ("minecraft", "Games"),
    ("chess.com", "Games"),
    ("lichess", "Games"),
    ("poki", "Games"),
    ("miniclip", "Games"),
    ("agar.io", "Games"),
    ("forge of empires", "Games"),
    ("catan universe", "Games"),
    # News & Current Affairs title keywords (after Video keywords — "svt" is safe here)
    ("svt nyheter", "News & Current Affairs"),
    ("svt", "News & Current Affairs"),
    ("dn.se", "News & Current Affairs"),
    ("dagens nyheter", "News & Current Affairs"),
    ("svd", "News & Current Affairs"),
    ("svenska dagbladet", "News & Current Affairs"),
    ("aftonbladet", "News & Current Affairs"),
    ("expressen", "News & Current Affairs"),
    ("göteborgs-posten", "News & Current Affairs"),
    ("goteborgs-posten", "News & Current Affairs"),
    ("gp.se", "News & Current Affairs"),
    ("sydsvenskan", "News & Current Affairs"),
    ("omni", "News & Current Affairs"),
    ("dagens industri", "News & Current Affairs"),
    ("di.se", "News & Current Affairs"),
    ("breakit", "News & Current Affairs"),
    ("ny teknik", "News & Current Affairs"),
    ("the guardian", "News & Current Affairs"),
    ("bbc", "News & Current Affairs"),
    ("cnn", "News & Current Affairs"),
    ("al jazeera", "News & Current Affairs"),
    ("reuters", "News & Current Affairs"),
    # Search & Navigation title keywords (last — very broad)
    ("google search", "Search & Navigation"),
    ("google", "Search & Navigation"),
    ("bing", "Search & Navigation"),
    ("duckduckgo", "Search & Navigation"),
    ("yahoo search", "Search & Navigation"),
    ("startpage", "Search & Navigation"),
    ("ecosia", "Search & Navigation"),
    ("kagi", "Search & Navigation"),
]

# App-name → study category mapping for non-browser applications.
# Faithfully derived from Matthias Lehner's APP_TO_CATEGORY dict (classifier 2026-07-06).
# Keys are lowercase app names (exact match, case-insensitive at runtime).
# "Excluded" means the app is deliberately suppressed — not a lookup miss.
APP_CATEGORY_MAP: dict[str, str] = {
    # AI chatbots & assistants
    "chatgpt": "AI Chatbots & Assistants",
    "chatgpt.exe": "AI Chatbots & Assistants",
    "claude": "AI Chatbots & Assistants",
    "claude.exe": "AI Chatbots & Assistants",
    "gemini": "AI Chatbots & Assistants",
    "microsoft copilot": "AI Chatbots & Assistants",
    "copilot": "AI Chatbots & Assistants",
    "perplexity": "AI Chatbots & Assistants",
    "poe": "AI Chatbots & Assistants",
    # Work & Productivity — Microsoft Office
    "microsoft word": "Work & Productivity",
    "word": "Work & Productivity",
    "winword.exe": "Work & Productivity",
    "microsoft excel": "Work & Productivity",
    "excel": "Work & Productivity",
    "excel.exe": "Work & Productivity",
    "microsoft powerpoint": "Work & Productivity",
    "powerpoint": "Work & Productivity",
    "powerpnt.exe": "Work & Productivity",
    # Email — Outlook is email, not productivity
    "microsoft outlook": "Email",
    "outlook": "Email",
    "outlook.exe": "Email",
    # Work & Productivity — collaboration/notes
    "microsoft teams": "Work & Productivity",
    "teams": "Work & Productivity",
    "zoom": "Work & Productivity",
    "zoom.us": "Work & Productivity",
    "notion": "Work & Productivity",
    "onenote": "Work & Productivity",
    "adobe acrobat": "Work & Productivity",
    "acrobat": "Work & Productivity",
    "preview": "Work & Productivity",
    "pages": "Work & Productivity",
    "numbers": "Work & Productivity",
    "keynote": "Work & Productivity",
    "libreoffice": "Work & Productivity",
    # Email — native clients
    "mail": "Email",
    "thunderbird": "Email",
    # Messaging
    "slack": "Messaging",
    "signal": "Messaging",
    "telegram": "Messaging",
    "whatsapp": "Messaging",
    "messenger": "Messaging",
    "discord": "Messaging",
    # Music & Audio
    "spotify": "Music & Audio",
    "music": "Music & Audio",
    "apple music": "Music & Audio",
    # Video Streaming — media players
    "vlc": "Video Streaming",
    "quicktime player": "Video Streaming",
    "netflix": "Video Streaming",
    # Games
    "steam": "Games",
    "epic games launcher": "Games",
    "battle.net": "Games",
    "roblox": "Games",
    "minecraft": "Games",
    "xbox": "Games",
    # Work & Productivity — creative/professional software
    "photoshop": "Work & Productivity",
    "illustrator": "Work & Productivity",
    "indesign": "Work & Productivity",
    "lightroom": "Work & Productivity",
    "premiere pro": "Work & Productivity",
    "final cut pro": "Work & Productivity",
    "figma": "Work & Productivity",
    "blender": "Work & Productivity",
    "autocad": "Work & Productivity",
    # System utilities — explicitly excluded (not a lookup miss)
    "finder": "Excluded",
    "explorer": "Excluded",
    "explorer.exe": "Excluded",
    "system settings": "Excluded",
    "settings": "Excluded",
    "system preferences": "Excluded",
    "terminal": "Excluded",
    "cmd.exe": "Excluded",
    "powershell.exe": "Excluded",
}


def build_toml_table(entries: list[tuple[str, str]]) -> str:
    seen: dict[str, str] = {}
    for pattern, category in entries:
        if pattern not in seen:
            seen[pattern] = category
    items = []
    for pattern, category in seen.items():
        k = pattern.replace("\\", "\\\\").replace('"', '\\"')
        v = category.replace("\\", "\\\\").replace('"', '\\"')
        items.append(f'"{k}" = "{v}"')
    return "\n".join(items)


# The flag must be matched anchored to line start. Since aw-watcher-window #137,
# config.py also documents the rewrite in a comment containing the literal text
# `sed -i 's/^research_enabled = false$/research_enabled = true/'`, and that
# comment appears *before* the real flag. An unanchored replace would patch the
# comment and leave research_enabled = false -- a green build with the Research
# Edition silently disabled.
ENABLED_FLAG_RE = re.compile(r"^research_enabled = false$", re.MULTILINE)

# Anchor for the post-#137 layout: research knobs moved out of `default_config`
# into a separate template so they are not persisted into every fresh install's
# config file.
RESEARCH_DEFAULTS_ANCHOR = 'research_defaults = """'

# Proof that the watcher can actually consume an app map (aw-watcher-window #136).
# This is a runtime-capability check, not a layout check, so it survives further
# reshuffling of the config templates.
APP_MAP_RUNTIME_MARKER = 'config.get("research_app_category_map"'


def patch_config(text: str) -> tuple[str, bool]:
    """Patch config.py text.  Returns (patched_text, app_map_injected)."""
    category_header = "[aw-watcher-window.research_category_map]"
    app_category_header = "[aw-watcher-window.research_app_category_map]"

    enabled_matches = len(ENABLED_FLAG_RE.findall(text))
    if enabled_matches != 1:
        raise ValueError(
            f"expected exactly one line-anchored 'research_enabled = false', found {enabled_matches}"
        )

    # Fail closed: without the runtime lookup the submodule predates PR #136, so
    # classify_app() does not exist and non-browser apps would keep their raw
    # names. Injecting anyway produces a green build that silently reproduces the
    # exact privacy bug this map fixes -- fail loudly instead.
    if APP_MAP_RUNTIME_MARKER not in text:
        raise ValueError(
            "aw-watcher-window does not read research_app_category_map "
            "(requires PR #136 in the submodule pin)"
        )

    entries = build_toml_table(CATEGORY_MAP)
    app_entries = build_toml_table(list(APP_CATEGORY_MAP.items()))

    if RESEARCH_DEFAULTS_ANCHOR in text:
        # Post-#137: the maps belong inside the `research_defaults` template.
        # That template is parsed standalone and merged into the
        # [aw-watcher-window] section key-by-key, so its table headers must NOT
        # carry the section prefix.
        block = (
            "research_enabled = true\n\n"
            f"[research_category_map]\n{entries}\n\n"
            f"[research_app_category_map]\n{app_entries}"
        )
        patched = ENABLED_FLAG_RE.sub(lambda _: block, text, count=1)
    else:
        # Pre-#137: the section-prefixed headers are already present in
        # `default_config`; inject the entries under them.
        if text.count(category_header) != 1:
            raise ValueError(f"expected exactly one '{category_header}' section")
        if text.count(app_category_header) != 1:
            raise ValueError(f"expected exactly one '{app_category_header}' section")
        patched = ENABLED_FLAG_RE.sub("research_enabled = true", text, count=1)
        patched = patched.replace(category_header, f"{category_header}\n{entries}", 1)
        patched = patched.replace(
            app_category_header, f"{app_category_header}\n{app_entries}", 1
        )

    return patched, True


def main() -> None:
    if not CONFIG_FILE.exists():
        print(f"Error: {CONFIG_FILE} not found", file=sys.stderr)
        sys.exit(1)
    text = CONFIG_FILE.read_text(encoding="utf-8")
    try:
        patched, app_map_injected = patch_config(text)
    except ValueError as error:
        print(f"Error: {error} in {CONFIG_FILE}", file=sys.stderr)
        sys.exit(1)
    CONFIG_FILE.write_text(patched, encoding="utf-8")
    unique = len({p for p, _ in CATEGORY_MAP})
    cats = len({c for _, c in CATEGORY_MAP})
    print(f"Injected {unique} unique patterns across {cats} categories into {CONFIG_FILE}")
    assert app_map_injected  # patch_config() now fails closed rather than skipping
    print(f"Injected {len(APP_CATEGORY_MAP)} app-name entries into {CONFIG_FILE}")


if __name__ == "__main__":
    main()
