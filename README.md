# Booble
Local search engine for your personal computer


<img width="256" height="256" alt="boobleicon" src="https://github.com/user-attachments/assets/718484ee-9713-4355-a3d1-4ad8aa3fd65d" />

Version 2.0.0 of the Booble local search engine has been released!

Booble is a desktop search engine that operates locally; it scans the content on your computer and displays the results. By visually mimicking a well-known search engine, it offers a familiar interface that enables you to perform searches more effectively and efficiently. It is coded using Python3 and Qt6. It is extremely lightweight and fast. It has minimal dependencies, fetching them directly from your Debian system's APT repository. It does not collect data or connect to the internet; it is simply a lightweight, bloatware-free piece of software that does its job.

<img width="1010" height="784" alt="Ekran görüntüsü_2026-09-28_02-30-22" src="https://github.com/user-attachments/assets/79d6ade4-3d8f-438c-8e9f-5b74c1b6b5eb" />
<img width="1010" height="784" alt="Ekran görüntüsü_2026-09-28_02-30-46" src="https://github.com/user-attachments/assets/29b72e8b-0a0e-48ed-965c-606a69cfab0c" />
<img width="1010" height="784" alt="Ekran görüntüsü_2026-09-28_02-31-40" src="https://github.com/user-attachments/assets/5eec42f5-10a4-4ac5-b5a0-90ca9a19e5d0" />


WHAT'S NEW:

The indexing algorithm has been completely overhauled, resulting in vastly increased speeds. Even scanning a large disk takes only seconds.

The long wait times previously experienced when initiating a new search from the results screen have been drastically reduced; additionally, a "busy indicator" (progress bar) now appears to prevent the program from looking like it has frozen.

Pagination buttons (1, 2, 3, etc.) now appear at the bottom of the page.

Items displayed in the results list use the system's default icon theme (retrieved from system files).

Items such as images and videos are displayed within a special container featuring a thumbnail, along with their properties (size and date).

The "Exclude" feature in the Settings menu has been improved and refined. Options such as "All," "Images," "Videos," "Audio," and "Documents" have been added to the search results page; selecting these filters the results to display only the chosen category.

The content of the "About" menu has been updated.

The application has been migrated from the legacy Qt5 interface engine to the modern Qt6 framework.

The application now supports dynamic translation based on gettext/po. It currently launches in English by default but can be switched to Turkish via the Help menu if desired.

PLANNED FUTURE IMPROVEMENTS:

I might move the radio buttons used for category-based filtering to the empty toolbar area at the top; this would be visually more appealing, as that space currently looks empty.

I could add more translations.

I am open to considering any suggestions you might have.

Despite its version number, the application is still in beta. Therefore, your feedback is highly valued. Please do not hesitate to share any issues you encounter or suggestions you may have.



