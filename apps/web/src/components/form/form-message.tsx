export function FormError({ message }: { message?: string }) {
  if (!message) return null;
  return (
    <p role="alert" className="rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
      {message}
    </p>
  );
}

export function FormNotice({ message }: { message?: string }) {
  if (!message) return null;
  return (
    <p role="status" className="rounded-lg border border-success/40 bg-success/10 px-3 py-2 text-sm">
      {message}
    </p>
  );
}
