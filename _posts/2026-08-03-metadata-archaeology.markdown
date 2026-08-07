---
title: Gems from the Vault
date: 2026-08-03
layout: default
description: Seven layers of metadata discovered while digging through my personal music collection
categories: data-forensics
---



<p class="dek">There's a lot that we don't know about the files that we accumulate. I'm sure that's true of many types of files, but for me it is most true of my music collection. If there's anything on my personal devices that's been hauled straight out of the sewers, it's as likely to be there as anywhere. </p>

## Understanding audio files

There was a time when I obsessed over bit rates and file formats. Those days are long gone. It's rare that I come across audio that doesn't sound good enough to my unsophisticated ear, and almost anything that I care about owning is easy to obtain as a FLAC. 

A second obsession of mine was tending my music collection's metadata. You might think that countless evenings spent pondering the finer points of how to classify music files is evidence of a wasted childhood. That may even be true. But with two decades of hindsight I am comfortable treating all of those hours as one of the more valuable learning experiences of those years, one that left with an appreciation for how difficult and complicated a seemingly simple task like assigning genres or classifying tracks by artist can be. 

But my focus was never much on the nuts and bolts of how this data is actually stored in an audio file. I put plenty of effort into finding the best interface to work with (remember Songbird?), but ultimately I was relying on that interface to make sense of the files for me. Exactly how the information I was obsessed with curating was stored on those files never mattered much to me except when I was experimenting with a new device or software tool and getting frustrated with it failing to appear as expected. 

What I learned from this exercise is that audio files are less a single metadata container than a potential stack of metadata containers. Like digging beneath the streets of a Mediterranean city, a scan of every file in my music collection unearthed layer after layer of history:
<div class="tablewrap" markdown="1">

| #   | Layer                                              | Found                                          |
| --- | -------------------------------------------------- | ---------------------------------------------- |
| 1   | Tag container (ID3v2, MP4 `ilst`, Vorbis comments) | 6,278                                          |
| 2   | Legacy shadow tags (ID3v1, APEv2)                  | 4,146                                          |
| 3   | Metadata **inside embedded cover art**             | EXIF 291, XMP 223, IPTC 293, JPEG comments 160 |
| 4   | Codec/stream headers (Xing/LAME)                   | 1,393 files                                    |
| 5   | Container padding (`free`/`skip` atoms)            | 1,282 B of residue                             |
| 6   | Filesystem (xattrs)                                | SELinux labels only                            |
| 7   | The audio signal itself                            | —                                              |

</div>

<p class="note">Both APEv2 and ID3v1 are at the tail of the file, so APEv2 was invisible unless ID3v1 was removed. On the first scan, none were found. After removing the ID3v1 tags, 195 were revealed.</p>

---
## Hidden Treasures

 When I started scanning these files, I didn't intend to do anything more than a deep-cleaning of two decades worth of accumulated metadata. Aside from learning more about how this data is stored  than I had ever intended to, I also unearthed some amusing finds, including:
 
**Six strangers' Apple IDs.** 73 files carried an `apID` atom for the iTunes Store
account that purchased them. Most of these were obviously real names! Whoever purchased these files never scrubbed their identity from them. 

**Someone's family photo tagging, nested inside album art.** This was the most amusing find. Cover art JPEG files can be nested inside of an audio file, and that nested file carries a metadata stack of its own. This is where I found tags like "Artist: Grandma & Bri", along with Photoshop CS4/CS5/CC, Picasa, and ACDSee version strings with timestamps from fifteen years ago. 

**An Amazon affiliate link with an AWS credential.** A WCOM frame held a 314-character nested Amazon redirect. At some point, someone had used a freeware tagger to fetch cover art from Amazon's Product Advertising API. While it was there, it wrote a "buy this" link into every file it touched, carrying its own affiliate tag that gave it a commission on the buyer's next 24 hours of purchases. The credential on this file is a type of access key that hasn't been in use for nearly two decades.

Other gems:

- breadcrumbs in the lyrics field — ranging from links to various music blogs, to torrent sites, to Telegram channels
- a cuesheet describing the genre of one track as "noisepop/candustrial/mathcore"
- All Music Guide catalog IDs from Windows Media Player
- trace markings from multiple generations of DJ software
- 4.5 MiB of cover art crammed into text frames


---

## Parting thoughts

I had more fun than I should have with a task that seemed like nothing more than a long-neglected chore. But it is also stuck with me: I had been hoarding these files for decades, moving them across probably dozens of devices, listening to some of them hundreds of times, and yet I had barely scratched the surface of what they really contained. 