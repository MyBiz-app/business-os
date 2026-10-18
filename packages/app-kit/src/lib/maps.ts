/** Navigation to a branch by link (Waze, Google Maps): no maps API key needed (#42). With the
 * branch's point on the map (R35) the link goes to that exact spot; without it, to the address. */
export type MapPoint = { latitude?: number | null; longitude?: number | null };

const exact = (point?: MapPoint) =>
  point?.latitude != null && point.longitude != null ? `${point.latitude},${point.longitude}` : null;

export function wazeLink(address: string, point?: MapPoint): string {
  const spot = exact(point);
  return spot ? `https://waze.com/ul?ll=${spot}&navigate=yes` : `https://waze.com/ul?q=${encodeURIComponent(address)}&navigate=yes`;
}

export function googleMapsLink(address: string, point?: MapPoint): string {
  const spot = exact(point);
  return `https://www.google.com/maps/dir/?api=1&destination=${spot ?? encodeURIComponent(address)}`;
}
