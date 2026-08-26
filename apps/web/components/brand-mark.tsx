import Image from "next/image";

import roadSignalMark from "../assets/roadsignal-mark.png";

export function BrandMark({ className }: { className?: string }) {
  return (
    <Image
      aria-hidden="true"
      alt=""
      className={className}
      data-roadsignal-logo=""
      height={64}
      priority
      sizes="48px"
      src={roadSignalMark}
      width={64}
    />
  );
}
