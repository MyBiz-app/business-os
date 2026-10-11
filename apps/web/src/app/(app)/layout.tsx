import { signOut } from "@/app/(auth)/actions";
import { AppHeader } from "@/components/app-header";
import { avatarSrc } from "@/components/avatar";
import { PaletteSync } from "@/components/palette";
import { UserMenu } from "@/components/user-menu";
import { getActiveMembership } from "@/lib/tenant";

export default async function AppLayout({ children }: LayoutProps<"/">) {
  const { me } = await getActiveMembership();

  return (
    <div className="flex flex-1 flex-col">
      <PaletteSync palette={me.palette ?? null} colors={me.palette_colors ?? null} />
      <AppHeader>
        <UserMenu
          id={me.id}
          name={me.full_name || me.email}
          email={me.email}
          avatar={avatarSrc(me.id, me.avatar_url)}
          platform={me.platform_admin}
          signOut={signOut}
        />
      </AppHeader>
      {children}
    </div>
  );
}
