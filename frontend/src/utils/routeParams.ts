import { useParams } from "react-router-dom";

export function useRequiredParam(name: string): string {
  const value = useParams()[name];
  if (!value) throw new Error(`Missing route param: ${name}`);
  return value;
}
