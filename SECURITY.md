# Security and privacy

Receipt exports can reveal addresses, store locations, partial payment details,
health-related purchases, and household routines. Keep real exports outside the
repository. The supplied `.gitignore` excludes the conventional export and
output directories, but review `git status` before every commit.

The Harris Teeter exporter opens a visible browser and waits for manual sign-in.
It never reads passwords, saves cookies in the export, or writes request headers.
Its dedicated browser profile remains on the local machine and should be treated
as sensitive.

Report security issues privately to the repository owner rather than opening a
public issue with receipt samples.
