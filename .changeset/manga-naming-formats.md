---
"comicarr": minor
---

Manga can now have its own folder and file names. **Settings → Media → Manga Naming** adds a manga folder format (for example `$Author/[$Year] $Series`, where `/` makes subfolders) and a manga file format (for example `$Series v$Volume c$Chapter`, using the issue zero-padding setting). Manga metadata has no English publisher, so `$Author` (and `$Publisher`) is the author and `$Year` the original start year. Like `$Annual` for comics, a number the file does not have is left out together with its letter, so a volume becomes `Gunnm v001`, a chapter `Gunnm c010.5`, and a range `Gunnm v001-003`. Both formats are empty by default, which keeps today's behaviour.

Adding a manga with a folder format that uses `/` or `$Publisher` no longer creates a folder such as `$Publisher-[1990] Gunnm`: each part becomes a real subfolder and the publisher is the author.
