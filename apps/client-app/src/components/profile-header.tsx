import * as ImagePicker from "expo-image-picker";
import { useCallback, useEffect, useState } from "react";
import { StyleSheet, View } from "react-native";
import { useTranslations } from "use-intl";

import { AuthImage } from "@business-os/app-kit/components/auth-image";
import { Avatar } from "@business-os/app-kit/components/rows";
import { Text } from "@business-os/app-kit/components/text";
import { useToast } from "@business-os/app-kit/components/toast";
import { Button, Card, ErrorText, Field, styles } from "@business-os/app-kit/components/ui";
import { unwrap } from "@business-os/app-kit/lib/api";
import { normalizeStatus, STATUS_MAX_LENGTH, statusChanged } from "@business-os/app-kit/lib/profile-status";
import { useBusiness } from "@/providers/business-provider";

const AVATAR_SIZE = 96;
type Me = { avatar_url?: string | null; status_text?: string | null };

/** The client's round picture (camera or gallery) and short status, at the top of the profile. */
export function ProfileHeader({ name }: { name: string }) {
  const t = useTranslations("client.profile");
  const toast = useToast();
  const { api: API, palette } = useBusiness();
  const [me, setMe] = useState<Me | null>(null);
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState<"photo" | "status" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const apply = useCallback((next: Me) => {
    setMe(next);
    setStatus(next.status_text ?? "");
  }, []);
  useEffect(() => {
    API.GET("/me")
      .then(unwrap)
      .then(apply)
      .catch(() => undefined);
  }, [API, apply]);

  const upload = async (result: ImagePicker.ImagePickerResult) => {
    const asset = result.canceled ? null : result.assets[0];
    if (!asset) return;
    setBusy("photo");
    setError(null);
    try {
      const form = new FormData();
      const type = asset.mimeType ?? "image/jpeg";
      if (asset.file) form.append("file", asset.file);
      else form.append("file", { uri: asset.uri, name: asset.fileName ?? "avatar.jpg", type } as unknown as Blob);
      const response = await API.PUT("/me/avatar", { body: form as never, bodySerializer: (body) => body });
      apply(unwrap(response));
      toast("success", t("photoSaved"));
    } catch {
      setError(t("photoFailed"));
    } finally {
      setBusy(null);
    }
  };

  // The picture is cropped to a square on the phone; the API keeps it small.
  const options: ImagePicker.ImagePickerOptions = { mediaTypes: ["images"], allowsEditing: true, aspect: [1, 1], quality: 0.7 };
  const fromGallery = async () => {
    const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) return setError(t("photoPermission"));
    await upload(await ImagePicker.launchImageLibraryAsync(options));
  };
  const fromCamera = async () => {
    const permission = await ImagePicker.requestCameraPermissionsAsync();
    if (!permission.granted) return setError(t("photoPermission"));
    await upload(await ImagePicker.launchCameraAsync(options));
  };
  const removePhoto = async () => {
    setBusy("photo");
    try {
      apply(unwrap(await API.DELETE("/me/avatar")));
    } catch {
      setError(t("photoFailed"));
    } finally {
      setBusy(null);
    }
  };

  const saveStatus = async () => {
    setBusy("status");
    setError(null);
    try {
      apply(unwrap(await API.PATCH("/me", { body: { status_text: normalizeStatus(status) ?? "" } })));
      toast("success", t("statusSaved"));
    } catch {
      setError(t("statusFailed"));
    } finally {
      setBusy(null);
    }
  };

  const avatarPath = me?.avatar_url ? `${me.avatar_url}` : null;
  return (
    <Card palette={palette}>
      <View style={local.center}>
        <View style={local.avatarBox}>
          <Avatar name={name} palette={palette} size={AVATAR_SIZE} />
          <View style={local.photo}>
            <AuthImage path={avatarPath} style={local.photoImage} label={t("photoLabel")} />
          </View>
        </View>
        <Text style={[styles.h2, { color: palette.foreground }]}>{name}</Text>
        {me?.status_text ? <Text style={[styles.muted, { color: palette.muted }]}>{me.status_text}</Text> : null}
      </View>
      <View style={local.row}>
        <View style={local.flex}>
          <Button label={t("takePhoto")} variant="secondary" palette={palette} busy={busy === "photo"} onPress={() => void fromCamera()} />
        </View>
        <View style={local.flex}>
          <Button label={t("choosePhoto")} variant="secondary" palette={palette} busy={busy === "photo"} onPress={() => void fromGallery()} />
        </View>
      </View>
      {me?.avatar_url ? <Button label={t("removePhoto")} variant="secondary" palette={palette} busy={busy === "photo"} onPress={() => void removePhoto()} /> : null}
      <Field
        label={t("status")}
        palette={palette}
        value={status}
        onChangeText={(value) => setStatus(value.slice(0, STATUS_MAX_LENGTH))}
        maxLength={STATUS_MAX_LENGTH}
        placeholder={t("statusPlaceholder")}
        hint={t("statusCount", { count: status.length, max: STATUS_MAX_LENGTH })}
      />
      <ErrorText message={error} palette={palette} />
      {statusChanged(status, me?.status_text) && (
        <Button label={t("saveStatus")} palette={palette} busy={busy === "status"} onPress={() => void saveStatus()} />
      )}
    </Card>
  );
}

const local = StyleSheet.create({
  center: { alignItems: "center", gap: 6 },
  avatarBox: { width: AVATAR_SIZE, height: AVATAR_SIZE },
  photo: { position: "absolute", top: 0, start: 0, width: AVATAR_SIZE, height: AVATAR_SIZE, borderRadius: AVATAR_SIZE / 2, overflow: "hidden" },
  photoImage: { width: AVATAR_SIZE, height: AVATAR_SIZE },
  row: { flexDirection: "row", gap: 8 },
  flex: { flex: 1 },
});
