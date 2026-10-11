/** Navigation to an address by link (Waze, Google Maps): no maps API key needed (#42). */
export function wazeLink(address: string): string {
  return `https://waze.com/ul?q=${encodeURIComponent(address)}&navigate=yes`;
}

export function googleMapsLink(address: string): string {
  return `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(address)}`;
}
