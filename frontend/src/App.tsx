import { createHashRouter, RouterProvider } from "react-router-dom";

import AddStonesView from "./views/AddStonesView";
import BuildMapView from "./views/BuildMapView";
import PlanView from "./views/PlanView";
import ProjectsView from "./views/ProjectsView";
import StonesView from "./views/StonesView";

const router = createHashRouter([
  { path: "/", element: <ProjectsView /> },
  { path: "/projects/:projectId/plan", element: <PlanView /> },
  { path: "/projects/:projectId/stones", element: <StonesView /> },
  { path: "/projects/:projectId/add-stones", element: <AddStonesView /> },
  { path: "/build/:buildMapId", element: <BuildMapView /> },
]);

export default function App() {
  return <RouterProvider router={router} />;
}
