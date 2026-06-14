import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { DataPage } from "./pages/DataPage";
import { Overview } from "./pages/Overview";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Overview />} />
          <Route path="workloads" element={<DataPage type="workloads" />} />
          <Route path="carbon" element={<DataPage type="carbon" />} />
          <Route path="scenarios" element={<DataPage type="scenarios" />} />
          <Route path="runs" element={<DataPage type="runs" />} />
          <Route path="placements" element={<DataPage type="placements" />} />
          <Route path="reports" element={<DataPage type="reports" />} />
          <Route path="admin" element={<DataPage type="admin" />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

