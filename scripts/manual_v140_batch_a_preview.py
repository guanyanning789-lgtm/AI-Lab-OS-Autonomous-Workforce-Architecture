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
    Item(r"C:\Users\PC\Downloads\ChatGPT Image 2026年8月14日 17_59_38.png", r"D:\AI-Lab\Media\Images\ChatGPT Image 2026年8月14日 17_59_38.png", "b48b7b0264ac933185d3ce87c4385c9b083ff324dda4e176fb0140b8f4acc290"),
    Item(r"C:\Users\PC\Downloads\Mobile Devices\IMG_8610.PNG", r"D:\AI-Lab\Media\Images\IMG_8610.PNG", "f23dc8d63f5198d411f6916daba02d34df08ac2dbd86bb3d60ed59b04e2f56c5"),
    Item(r"C:\Users\PC\Desktop\1af335ef-7f1c-4c7d-ad05-dc30857f0b4c.png", r"D:\AI-Lab\Media\Images\1af335ef-7f1c-4c7d-ad05-dc30857f0b4c.png", "9a409c4f6b8a10a7445360c5ad78b2410abc6ee00ac3a92acde1b128c8004f87"),
    Item(r"C:\Users\PC\Desktop\30bcf35b-f2c9-4661-bc07-dbe6723467a2.png", r"D:\AI-Lab\Media\Images\30bcf35b-f2c9-4661-bc07-dbe6723467a2.png", "c78e5a73164d7d21778e6dc56eaee878892265065ece0265c3e7e57bdda2550a"),
    Item(r"C:\Users\PC\Desktop\6ad26828-eb8c-4671-8518-2f3a53c524a9.png", r"D:\AI-Lab\Media\Images\6ad26828-eb8c-4671-8518-2f3a53c524a9.png", "0af66801ebac0fa1e228f9728851704c07975d93afa3ca0cfc213a703c10f8e2"),
    Item(r"C:\Users\PC\Desktop\coe.png", r"D:\AI-Lab\Media\Images\coe.png", "6b6186226f140208ba76cb6fe051047e82fdadbbab57625040c8df42087e155f"),
    Item(r"C:\Users\PC\Desktop\任務調度中心.png", r"D:\AI-Lab\Media\Images\任務調度中心.png", "e0b0d711bfea0c96a19629a664fbc66bf752aaa08b8d42e553dd97c8f959ce79"),
    Item(r"C:\Users\PC\Desktop\内容創作.png", r"D:\AI-Lab\Media\Images\内容創作.png", "112f36b67b9b0cfb3d1d5dc481af91e5f40d9df5420612ba5896126cdda6319f"),
)


def digest() -> str:
    payload = [{"source": i.source, "destination": i.destination, "action": "migrate", "sha256": i.sha256} for i in ITEMS]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def main() -> int:
    print("=" * 78)
    print("STORAGE CURATOR V1.4.0 BATCH A EXACT APPROVAL PREVIEW")
    print("=" * 78)
    ready = True
    for index, item in enumerate(ITEMS, 1):
        source = Path(item.source)
        destination = Path(item.destination)
        source_ok = source.exists() and source.is_file()
        destination_free = not destination.exists()
        print(f"{index}. {item.source}")
        print(f"   -> {item.destination}")
        print(f"   SOURCE_OK={source_ok} DESTINATION_FREE={destination_free}")
        ready = ready and source_ok and destination_free
    print(f"BATCH_ITEMS = {len(ITEMS)}")
    print(f"CONTRACT_DIGEST = {digest()}")
    print(f"READY = {ready}")
    print("APPROVED = False")
    print("EXECUTED = False")
    print("RESULT = BATCH_A_PREVIEW")
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
