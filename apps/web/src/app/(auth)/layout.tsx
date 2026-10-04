import { AppHeader } from "@/components/app-header";

export default function AuthLayout({ children }: LayoutProps<"/">) {
  return (
    <div className="flex flex-1 flex-col">
      <AppHeader />
      <main className="enter flex flex-1 items-start justify-center px-4 py-16">
        <div className="flex w-full max-w-sm flex-col gap-6 card p-6 sm:p-8">
          {children}
        </div>
      </main>
    </div>
  );
}
