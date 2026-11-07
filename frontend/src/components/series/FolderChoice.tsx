/**
 * Fork: pick a folder from a short list (the same folder under each library
 * root), or type another one. Used by the series folder and add dialogs.
 */
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export const OTHER_FOLDER = "__other__";

export interface FolderChoiceOption {
  value: string;
  label: string;
  hint?: string;
}

interface FolderChoiceProps {
  name: string;
  options: FolderChoiceOption[];
  /** The selected option value, or OTHER_FOLDER. */
  selected: string;
  onSelect: (value: string) => void;
  other: string;
  onOtherChange: (value: string) => void;
  /** Placeholder for the typed folder. */
  placeholder?: string;
  loading?: boolean;
}

export function FolderChoice({
  name,
  options,
  selected,
  onSelect,
  other,
  onOtherChange,
  placeholder = "/comics/Magazines/Wizard",
  loading = false,
}: FolderChoiceProps) {
  const otherId = `${name}-other`;
  return (
    <fieldset className="grid gap-2">
      <legend className="mb-1 text-sm font-medium">Folder</legend>
      {loading ? (
        <p className="text-xs text-muted-foreground">Loading library roots…</p>
      ) : null}
      {options.map((option) => (
        <label
          key={option.value}
          className="flex items-start gap-2 text-sm"
          data-testid="folder-choice-option"
        >
          <input
            type="radio"
            name={name}
            value={option.value}
            checked={selected === option.value}
            onChange={() => onSelect(option.value)}
            className="mt-1 accent-primary"
          />
          <span className="min-w-0">
            <span className="block break-all font-mono text-xs">
              {option.label}
            </span>
            {option.hint ? (
              <span className="block text-xs text-muted-foreground">
                {option.hint}
              </span>
            ) : null}
          </span>
        </label>
      ))}
      <label className="flex items-start gap-2 text-sm">
        <input
          type="radio"
          name={name}
          value={OTHER_FOLDER}
          checked={selected === OTHER_FOLDER}
          onChange={() => onSelect(OTHER_FOLDER)}
          className="mt-1 accent-primary"
        />
        <span>Another folder</span>
      </label>
      {selected === OTHER_FOLDER ? (
        <div className="grid gap-1.5 pl-6">
          <Label htmlFor={otherId} className="sr-only">
            Folder
          </Label>
          <Input
            id={otherId}
            value={other}
            onChange={(event) => onOtherChange(event.target.value)}
            placeholder={placeholder}
            className="font-mono"
            autoComplete="off"
            spellCheck={false}
            autoFocus
          />
          <p className="text-xs text-muted-foreground">
            Use the path Comicarr sees. In Docker, that is the path inside the
            container. It must be inside a library root.
          </p>
        </div>
      ) : null}
    </fieldset>
  );
}
