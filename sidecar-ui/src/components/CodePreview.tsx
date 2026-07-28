import { useMemo } from "react";
import hljs from "highlight.js/lib/core";
import python from "highlight.js/lib/languages/python";

hljs.registerLanguage("python", python);

const PLACEHOLDER = "# Describe or build a playbook to see Python source";

interface CodePreviewProps {
  source: string;
  className?: string;
  id?: string;
}

export function CodePreview({ source, className, id }: CodePreviewProps) {
  const highlighted = useMemo(() => {
    const code = source.trim();
    if (!code) return null;
    try {
      return hljs.highlight(code, { language: "python" }).value;
    } catch {
      return null;
    }
  }, [source]);

  if (!highlighted) {
    return (
      <pre id={id} className={className}>
        <code>{source || PLACEHOLDER}</code>
      </pre>
    );
  }

  return (
    <pre id={id} className={className}>
      <code
        className="hljs language-python"
        dangerouslySetInnerHTML={{ __html: highlighted }}
      />
    </pre>
  );
}
