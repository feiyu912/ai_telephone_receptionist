import { SVGProps } from "react";

export type PropsType = SVGProps<SVGSVGElement>;

export function ChevronUp(props: PropsType) {
  return (
    <svg
      width={16}
      height={8}
      viewBox="0 0 16 8"
      fill="currentColor"
      {...props}
    >
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        d="M7.553.728a.687.687 0 01.895 0l6.416 5.5a.688.688 0 01-.895 1.044L8 2.155 2.03 7.272a.688.688 0 11-.894-1.044l6.417-5.5z"
      />
    </svg>
  );
}

export function ArrowLeftIcon(props: PropsType) {
  return (
    <svg
      width="32"
      height="32"
      viewBox="0 0 32 32"
      fill="none"
      {...props}
    >
      <path
        d="M20 8L12 16L20 24"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
