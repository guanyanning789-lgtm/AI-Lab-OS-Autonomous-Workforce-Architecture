from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Item:
    source: str
    destination: str
    sha256: str


ITEMS = (
    Item(r"C:\Users\PC\Desktop\學習計劃.png", r"D:\AI-Lab\Media\Images\學習計劃.png", "de41bca1842bed702fac9efd2fcaa751721aa6f5cb8de3ba18ab592699e0573e"),
    Item(r"C:\Users\PC\Desktop\文件管理員.png", r"D:\AI-Lab\Media\Images\文件管理員.png", "98997461b7ee0ecca8c0e8e904ee6738301c55ccae0d411b52a5574974f5672f"),
    Item(r"C:\Users\PC\Desktop\瀏覽器專家.png", r"D:\AI-Lab\Media\Images\瀏覽器專家.png", "9cdf30352f6266f3522c28daf4a0c7dcedaf1000399ab2b446b6502b1fa7b157"),
    Item(r"C:\Users\PC\Desktop\生活管理.png", r"D:\AI-Lab\Media\Images\生活管理.png", "5976000259441abce2c66324baf789a366a948ee4f371b86666c768ac05feb27"),
    Item(r"C:\Users\PC\Desktop\知識管理員.png", r"D:\AI-Lab\Media\Images\知識管理員.png", "b18c97a0558b5b83beaf289efe8e8bb7e07588fa28803d541c895155dfb20a9e"),
    Item(r"C:\Users\PC\Desktop\研究分析.png", r"D:\AI-Lab\Media\Images\研究分析.png", "f5bcd74ffafe5ebe33d7fb937e84ea7785cf5a8988fe1ea6673a8bc57e524c5b"),
    Item(r"C:\Users\PC\Desktop\系統操作員.png", r"D:\AI-Lab\Media\Images\系統操作員.png", "054e0346d901d4153a8befe5cd9d842f31b3c64299d1310dac8c82a943e8669b"),
)


def digest() -> str:
    payload = [
        {"source": i.source, "destination": i.destination, "action": "migrate", "sha256": i.sha256}
        for i in ITEMS
    ]
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    print("=" * 78)
    print("STORAGE CURATOR V1.4.2 BATCH B EXACT APPROVAL PREVIEW")
    print("=" * 78)
    ready = True
    for index, item in enumerate(ITEMS, 1):
        source = Path(item.source)
        destination = Path(item.destination)
        source_ok = source.exists() and source.is_file()
        hash_ok = source_ok and sha256(source) == item.sha256
        destination_free = not destination.exists()
        print(f"{index}. {item.source}")
        print(f"   -> {item.destination}")
        print(f"   SOURCE_OK={source_ok} HASH_OK={hash_ok} DESTINATION_FREE={destination_free}")
        ready = ready and source_ok and hash_ok and destination_free
    print(f"BATCH_ITEMS = {len(ITEMS)}")
    print(f"CONTRACT_DIGEST = {digest()}")
    print(f"READY = {ready}")
    print("APPROVED = False")
    print("EXECUTED = False")
    print("RESULT = BATCH_B_PREVIEW")
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
