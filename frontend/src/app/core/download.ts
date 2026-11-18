// Enregistre un fichier reçu du serveur (ex. un PDF) sur l'appareil de l'utilisateur.
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.rel = 'noopener';
  document.body.appendChild(link);
  link.click();
  link.remove();
  // On laisse au navigateur le temps de lancer le téléchargement avant de libérer la mémoire.
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}
