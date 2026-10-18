import { redirect } from "next/navigation";

/** Events moved into the quotes page (a slicer between quotes and events); old links keep working. */
export default function EventsPage() {
  redirect("/quotes?view=events");
}
