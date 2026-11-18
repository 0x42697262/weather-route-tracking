type FieldMessageProps = Readonly<{
  id: string;
  error: string | undefined;
  hint?: string | undefined;
}>;

export function FieldMessage({ id, error, hint }: FieldMessageProps) {
  if (error !== undefined) {
    return (
      <p id={id} className="text-sm text-destructive">
        {error}
      </p>
    );
  }
  if (hint === undefined) {
    return null;
  }
  return (
    <p id={id} className="text-xs text-muted-foreground">
      {hint}
    </p>
  );
}
