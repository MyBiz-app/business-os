import AsyncStorage from "@react-native-async-storage/async-storage";

import { rememberedIn } from "./remembered-core";

/** What the app remembers on this phone; never throws (see `rememberedIn`). */
export const remembered = rememberedIn(AsyncStorage);
